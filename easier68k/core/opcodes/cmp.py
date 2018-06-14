from ...core.enum.ea_mode import EAMode
from ...core.enum.op_size import MoveSize, OpSize
from ...core.enum import ea_mode_bin
from ...core.enum.ea_mode_bin import parse_ea_from_binary
from ...simulator.m68k import M68K
from ...core.opcodes.opcode import Opcode
from ...core.util.split_bits import split_bits
from ...core.util import opcode_util
from ..util.parsing import parse_assembly_parameter
from ..models.assembly_parameter import AssemblyParameter
from ..enum.condition_status_code import ConditionStatusCode
from ..models.memory_value import MemoryValue

# foward declaration for specifying the return type
class Cmp(Opcode):
    pass

class Cmp(Opcode):
    """
    CMP (Page 179 of M68000PRM)

    Subtracts the source operand from the destination operand and
    set the condition codes accordingly. The destination must be a
    data register. The destination is not modified by this instruction.

    Note: CMPA is used when the destination is an address register.
    CMPI is used when the source is immediate data. CMPM is used
    for memory-to-memory compares.

    CCR bits modified by this instruction:
    X Unset
    N Set
    Z Set
    V Set
    C Set
    """

    # the allowed sizes for this opcode
    valid_sizes = [OpSize.BYTE, OpSize.WORD, OpSize.LONG]

    def __init__(self, params: list, size: OpSize = OpSize.WORD):
        # ensure that the parameters are valid
        assert len(params) == 2
        assert isinstance(params[0], AssemblyParameter)
        assert isinstance(params[1], AssemblyParameter)

        # source (params[0]) can be any EA mode
        # ensure that the destination is Dn
        assert params[1].mode == EAMode.DataRegisterDirect

        self.src = params[0]
        self.dest = params[1]

        assert size in Cmp.valid_sizes
        self.size = size

    def assemble(self) -> bytearray:
        """
        Assembles this opcode into a bytearray to be inserted into memory
        :return: The bytearray which represents this assembled opcode
        """

        # 1 0 1 1 Dest Register xxx OpMode xxx EA mode xxx Register xxx
        ret_opcode = 0b1011 << 12
        # add the dest register in it's place
        ret_opcode |= self.dest.data << 9
        # add the OpMode bytes
        if self.size == OpSize.BYTE:
            ret_opcode |= 0b000 << 6
        elif self.size == OpSize.WORD:
            ret_opcode |= 0b001 << 6
        elif self.size == OpSize.LONG:
            ret_opcode |= 0b010 << 6

        # add the ea bits for the src
        # with mode first
        ret_opcode |= ea_mode_bin.parse_from_ea_mode_modefirst(self.src)

        # convert the int to bytes, then to a mutable bytearray
        return bytearray(ret_opcode.to_bytes(2, byteorder='big', signed=False))

    def execute(self, simulator: M68K):
        """
        Executes this command in the simulator

        Subtracts the source operand from the destination operand and
        set the condition codes accordingly. The destination must be a
        data register. The destination is not modified by this instruction.

        :param simulator:
        :return:
        """

        # get the src and dest values
        src_val = self.src.get_value(simulator, self.size.get_number_of_bytes())
        dest_val = self.dest.get_value(simulator, self.size.get_number_of_bytes())

        comparision = src_val.get_value_signed() - dest_val.get_value_signed()
        comp_mv = src_val - dest_val

        overflow = False
        # if the two values have the same MSB
        if src_val.get_negative() == dest_val.get_negative():
            # and after subtracting have a different MSB
            # then there has been an overflow
            if src_val.get_negative() != comp_mv.get_negative():
                overflow = True

        # ignore the carry bit

        # set negative w/ (dest - src) < 0
        simulator.set_condition_status_code(ConditionStatusCode.Negative, comparision < 0)
        # set zero w/ (dest_val - src_val) == 0
        simulator.set_condition_status_code(ConditionStatusCode.Zero, comparision == 0)
        # set if an overflow occurs
        simulator.set_condition_status_code(ConditionStatusCode.Overflow, overflow)
        # set if a borrow occurs
        # (this is the same as if src > dest)
        simulator.set_condition_status_code(ConditionStatusCode.Carry, src_val > dest_val)

        # set the number of bytes to increment equal to the length of the
        # instruction (1 word)
        to_increment = OpSize.WORD.value

        if self.src.mode is EAMode.AbsoluteLongAddress:
            to_increment += OpSize.LONG.value
        if self.src.mode is EAMode.AbsoluteWordAddress:
            to_increment += OpSize.WORD.value

        # increment PC
        simulator.increment_program_counter(to_increment)

    def __str__(self):
        return 'CMP Size {}, Src {}, Dest {}'.format(self.size, self.src, self.dest)

    @classmethod
    def command_matches(cls, command: str) -> bool:
        """
        Checks whether a command string is an instance of this command type

        This will only allow for CMP. Not CMPA, CMPI, CMPM. While CMP is not
        checking for the types that would make it actually one of these
        different types, those instructions must be implemented separately.

        :param command: The command string to check 'CMP.W', 'CMP'
        :return: Whether the string is an instance of CMP
        """
        return opcode_util.command_matches(command, 'CMP')

    @classmethod
    def get_word_length(cls, command: str, parameters: str) -> int:
        """
        Gets the length of this command in memory

        >>> Cmp.get_word_length('CMP', 'D0, D1')
        1

        >>> Cmp.get_word_length('CMP.W', 'D0, D1')
        1

        >>> Cmp.get_word_length('CMP.L', 'D0, D1')
        1

        >>> Cmp.get_word_length('CMP.L', '($AAAA).L, D7')
        3

        :param command:
        :param parameters:
        :return:
        """
        # split the command to get the size, if specified
        parts = command.split('.')
        if len(parts) == 1:
            size = OpSize.WORD
        else:
            size = OpSize.parse(parts[1])

        params = parameters.split(',')

        # parse the src and dest parameters

        src = parse_assembly_parameter(params[0].strip())
        dest = parse_assembly_parameter(params[1].strip())

        # minimum length is always 1
        length = 1

        if src.mode == EAMode.IMM:
            # immediate data is 2 words long
            if size == OpSize.LONG:
                length += 2
            else:
                # bytes and words are 1 word long
                length += 1

        if src.mode == EAMode.AWA:
            # appends a word
            length += 1

        if src.mode == EAMode.ALA:
            # appends a long
            length += 2

        return length

    @classmethod
    def is_valid(cls, command: str, parameters: str) -> (bool, list):
        """
        Tests whether the given command is valid

        >>> Cmp.is_valid('CMP', 'D0, D1')[0]
        True

        >>> Cmp.is_valid('CMP.', '#123, D7')[0]
        False

        :param command:
        :param parameters:
        :return:
        """
        # don't bother with param invalid modes
        return opcode_util.n_param_from_str(
            command,
            parameters,
            "CMP",
            2)

    @classmethod
    def disassemble_instruction(cls, data: bytes) -> Opcode:
        """
        Disassembles the instruction into an instance of the CMP class
        :param data:
        :return:
        """
        assert len(data) >= 2, 'Opcode size must be at least 1 word'

        first_word = int.from_bytes(data[0:2], 'big')
        [opcode_bin,
         register_bin,
         opmode_bin,
         ea_mode_bin,
         ea_reg_bin] = split_bits(first_word, [4, 3, 3, 3, 3])

        # ensure that this is the correct opcode
        if opcode_bin != 0b1011:
            return None

        src = None
        dest = None
        size = None
        words_used = 1

        if opmode_bin == 0b000:
            size = OpSize.BYTE
        elif opcode_bin == 0b001:
            size = OpSize.WORD
        elif opcode_bin == 0b010:
            size = OpSize.LONG
        else:
            return None

        src = parse_ea_from_binary(ea_mode_bin, ea_reg_bin, size, True, data[words_used * 2:])[0]
        dest = AssemblyParameter(EAMode.DRD, register_bin)

        # make a new reference of this type
        return cls([src, dest], size)