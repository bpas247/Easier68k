"""
Tests for the CMP opcode
Ensures that all of the CCR bits are being set correctly
"""

from easier68k.simulator.m68k import M68K
from easier68k.core.opcodes.cmp import Cmp
from easier68k.core.models.assembly_parameter import AssemblyParameter
from easier68k.core.enum.ea_mode import EAMode
from easier68k.core.enum.register import Register
from easier68k.core.enum.op_size import OpSize
from easier68k.core.enum.condition_status_code import ConditionStatusCode
from easier68k.core.util.parsing import parse_assembly_parameter
from easier68k.core.models.memory_value import MemoryValue

def test_cmp():
    """
    Test to see that CMP sets the CCR bits
    :return:
    """
    sim = M68K()
    sim.set_program_counter_value(0x1000)

    # initialize the values of D0 and D1
    sim.set_register(Register.D0, MemoryValue(OpSize.WORD, unsigned_int=0x00c0ffee))
    sim.set_register(Register.D1, MemoryValue(OpSize.WORD, unsigned_int=123))

    # compare D0 to D1
    params = [AssemblyParameter(EAMode.DRD, 0), AssemblyParameter(EAMode.DRD, 1)]
    cmp = Cmp(params, OpSize.BYTE)
    cmp.execute(sim)

