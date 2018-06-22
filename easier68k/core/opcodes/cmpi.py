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
from ..models.memory_value import MemoryValue, mask_value_for_length


# foward declaration for specifying the return type
class Cmpi(Opcode):
    pass


class Cmpi(Opcode):
    """
    CMPI (Page 4-79 of M68000PRM)

    Subtracts the immediate data from the destination operand and sets the condition codes according to the result
    ; the destination location is not changed.
    The size of the operation may be speciﬁed as byte, word, or long.
    The size of the immediate data matches the operation size.

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

        # source can only be immediate data
        assert params[0].mode == EAMode.Immediate

        # destination can be any EA mode
        # except for An and immediate
        assert params[1].mode != EAMode.AddressRegisterDirect and params[1].mode != EAMode.Immediate

        self.src = params[0]
        self.dest = params[1]

        assert size in Cmpi.valid_sizes
        self.size = size

    def assemble(self) -> bytearray:
        """
        Assembles this opcode into a bytearray to be inserted into memory
        :return: The bytearray which represents this assembled opcode
        """

        # 0 0 0 0 1 1 0 0 size xx EA mode xxx Register xxx
        ret_opcode = 0b00001100 << 8
        # add the size
        if self.size == OpSize.BYTE:
            ret_opcode |= 0b00 << 6
        elif self.size == OpSize.WORD:
            ret_opcode |= 0b01 << 6
        elif self.size == OpSize.LONG:
            ret_opcode |= 0b10 << 6

        ret_opcode |= ea_mode_bin.parse_from_ea_mode_modefirst(self.dest) << 0

        ret_bytes = bytearray(ret_opcode.to_bytes(2, byteorder='big', signed=False))

        # extend to include source
        ret_bytes.extend(opcode_util.ea_to_binary_post_op(self.src, self.size).get_value_bytearray())

        # extend to include destination (if needed)
        if self.dest.mode == EAMode.IMM or self.dest.mode == EAMode.AWA or self.dest.mode == EAMode.ALA:
            ret_bytes.extend(opcode_util.ea_to_binary_post_op(self.dest, self.size).get_value_bytearray())

        return ret_bytes

    def execute(self, simulator: M68K):
        """
        Executes this command in the simulator

        Subtracts the source operand from the destination operand and
        set the condition codes accordingly. The source must be an
        immediate number. The destination is not modified by this instruction.

        :param simulator: the simulator that this opcode is being run on
        :return:
        """

        # get the src and dest values
        src_val = self.src.get_value(simulator, self.size.get_number_of_bytes())
        dest_val = self.dest.get_value(simulator, self.size.get_number_of_bytes())

        comparison = dest_val.get_value_signed() - src_val.get_value_signed()
        raw_total = dest_val.get_value_unsigned() - src_val.get_value_unsigned()
        comp_mv = dest_val - src_val

        # mask out only the bits we need/want
        comp_mv = MemoryValue(self.size,
                              unsigned_int=mask_value_for_length(self.size, comp_mv.get_value_unsigned()))

        print("comparison: " + str(comparison))
        print("comp_mv: " + str(comp_mv))

        negative = False

        if self.size is OpSize.BYTE:
            negative = comparison & 0x80 > 0
        elif self.size is OpSize.WORD:
            negative = comparison & 0x8000 > 0
        elif self.size is OpSize.LONG:
            negative = comparison & 0x80000000 > 0

        # Overflow occurs when a sign change occurs where it shouldn't occur.
        # For example: positive - negative != negative.
        # This doesn't make sense, so an overflow occurs
        overflow = False

        if src_val.get_negative() is False:
            if dest_val.get_negative() is True:
                if raw_total > 0 and raw_total & 0x80000000 > 0:
                    overflow = True

        # set negative w/ (dest - src) < 0
        simulator.set_condition_status_code(ConditionStatusCode.Negative, negative)
        # set zero w/ (dest_val - src_val) == 0
        simulator.set_condition_status_code(ConditionStatusCode.Zero, comparison == 0)
        # set if an overflow occurs
        simulator.set_condition_status_code(ConditionStatusCode.Overflow, overflow)
        # set if a borrow occurs
        # (this is the same as if src > dest)
        simulator.set_condition_status_code(ConditionStatusCode.Carry, raw_total < 0)

        # set the number of bytes to increment equal to the length of the
        # instruction (1 word)
        to_increment = OpSize.WORD.value

        # Increment by size
        to_increment += OpSize.LONG.value if self.size == OpSize.LONG else OpSize.WORD.value

        # any additional increments by destination value
        if self.dest.mode is EAMode.AbsoluteLongAddress:
            to_increment += OpSize.LONG.value
        if self.dest.mode is EAMode.AbsoluteWordAddress:
            to_increment += OpSize.WORD.value

        # increment PC
        simulator.increment_program_counter(to_increment)

    def __str__(self):
        return 'CMPI Size {}, Src {}, Dest {}'.format(self.size, self.src, self.dest)

    @classmethod
    def command_matches(cls, command: str) -> bool:
        """
        Checks whether a command string is an instance of this command type

        This will only allow for CMPI. Not CMPA, CMP, CMPM. While CMPI is not
        checking for the types that would make it actually one of these
        different types, those instructions must be implemented separately.

        :param command: The command string to check 'CMPI.W', 'CMPI'
        :return: Whether the string is an instance of CMPI
        """
        return opcode_util.command_matches(command, 'CMPI')

    @classmethod
    def get_word_length(cls, command: str, parameters: str) -> int:
        """
        Gets the length of this command in memory, including the length of
        the single opcode and the length of any immediate parameter values

        >>> Cmpi.get_word_length('CMPI', '#123, D3')
        2

        >>> Cmpi.get_word_length('CMPI.L', '#12345678, D1')
        3

        >>> Cmpi.get_word_length('CMPI.W', '#$FFFF, (A2)+')
        2

        >>> Cmpi.get_word_length('CMPI.L', '#12345678, (A7)')
        3

        >>> Cmpi.get_word_length('CMPI.W', '#$FFFF, ($AAAA).W')
        3

        >>> Cmpi.get_word_length('CMPI.L', '#12345678, ($AAAA).L')
        5

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

        # length is at least either 2 or 3 depending on size
        length = 3 if size == OpSize.LONG else 2

        if dest.mode == EAMode.AWA:
            # appends a word
            length += 1

        if dest.mode == EAMode.ALA:
            # appends a long
            length += 2

        return length

    @classmethod
    def is_valid(cls, command: str, parameters: str) -> (bool, list):
        """
        Tests whether the given command is valid

        >>> Cmpi.is_valid('CMPI', '#123, D1')[0]
        True

        >>> Cmpi.is_valid('CMP.', '#123, D7')[0]
        False

        :param command:
        :param parameters:
        :return:
        """
        # don't bother with param invalid modes
        return opcode_util.n_param_is_valid(
            command,
            parameters,
            "CMPI",
            2)

    @classmethod
    def disassemble_instruction(cls, data: bytes) -> Opcode:
        """
        CMPI.W #123,D7
        >>> op = Cmpi.disassemble_instruction(bytearray.fromhex('0C47007B'))

        >>> str(op.src)
        'EA Mode: EAMode.IMM, Data: 123'

        >>> str(op.dest)
        'EA Mode: EAMode.DRD, Data: 7'

        Disassembles the instruction into an instance of the CMP class
        :param data:
        :return:
        """
        assert len(data) >= 2, 'Opcode size must be at least 1 word'

        first_word = int.from_bytes(data[0:2], 'big')
        [opcode_bin,
         size_bin,
         ea_mode_binary,
         ea_reg_bin] = split_bits(first_word, [8, 2, 3, 3])

        # ensure that this is the correct opcode
        if opcode_bin != 0b00001100:
            return None

        src = None
        dest = None
        size = None
        words_used = 1

        if size_bin == 0b00:
            size = OpSize.BYTE
        elif size_bin == 0b01:
            size = OpSize.WORD
        elif size_bin == 0b10:
            size = OpSize.LONG
        else:
            return None

        src_size = 4 if size == OpSize.LONG else 2
        src_value = int.from_bytes(data[2:2+src_size], 'big')

        src = AssemblyParameter(EAMode.Immediate, src_value)
        dest = parse_ea_from_binary(ea_mode_binary, ea_reg_bin, size, True, data[words_used * 2:])[0]

        # make a new reference of this type
        return cls([src, dest], size)