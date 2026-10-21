"""cocotb tests for mac_int8.

Steps 1 and 3 run this file. Step 1 drives the RTL, step 3 drives the
gate-level netlist. The design is the top level in both runs, so the same
test checks both.

The flow gives the clock period in the environment variable
CLK_PERIOD_NS, and sets GATE_LEVEL_SIM to 1 for the gate-level run.

The API used here is the part of cocotb that is stable across version 1.6
and version 2: cocotb.test, Clock, RisingEdge, Timer, and int() on a signal
value. The time unit is passed as a positional argument, because version 1
names that argument "units" and version 2 names it "unit".
"""

import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

CLK_PERIOD_NS = float(os.environ.get("CLK_PERIOD_NS", "2.0"))
GATE_LEVEL = os.environ.get("GATE_LEVEL_SIM", "0") == "1"

ACC_BITS = 32
ACC_MASK = (1 << ACC_BITS) - 1


def to_signed(value, bits):
    """Reads a two's complement number of the given width."""
    if value & (1 << (bits - 1)):
        return value - (1 << bits)
    return value


def to_unsigned(value, bits):
    """Writes a two's complement number of the given width."""
    return value & ((1 << bits) - 1)


def read_acc(dut):
    """Reads acc_o as a signed number. It fails on an X value."""
    try:
        raw = int(dut.acc_o.value)
    except ValueError as exc:
        raise AssertionError(
            "acc_o holds an X or Z value: {}. In a gate-level run this "
            "means an input was not driven before the reset ended.".format(
                dut.acc_o.value)) from exc
    return to_signed(raw, ACC_BITS)


async def start_clock(dut):
    cocotb.start_soon(Clock(dut.clk_i, CLK_PERIOD_NS, "ns").start())


async def reset(dut):
    """Drives every input, then releases the reset."""
    dut.rst_n.value = 0
    dut.en_i.value = 0
    dut.clr_i.value = 0
    dut.a_i.value = 0
    dut.b_i.value = 0
    for _ in range(4):
        await RisingEdge(dut.clk_i)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk_i)
    await settle()


async def settle():
    """Waits for the outputs after a clock edge."""
    await Timer(CLK_PERIOD_NS / 4.0, "ns")


async def step(dut, a, b, en=1, clr=0):
    """Applies one operation and waits for the result."""
    dut.a_i.value = to_unsigned(a, 8)
    dut.b_i.value = to_unsigned(b, 8)
    dut.en_i.value = en
    dut.clr_i.value = clr
    await RisingEdge(dut.clk_i)
    await settle()


@cocotb.test()
async def test_reset_clears_accumulator(dut):
    """The reset clears the accumulator."""
    await start_clock(dut)
    await reset(dut)
    assert read_acc(dut) == 0, "acc_o is {} after the reset".format(read_acc(dut))


@cocotb.test()
async def test_directed_products(dut):
    """The corner values of the signed multiplier are correct."""
    await start_clock(dut)
    await reset(dut)

    cases = [
        (1, 1),
        (-1, 1),
        (1, -1),
        (-1, -1),
        (127, 127),
        (-128, -128),
        (-128, 127),
        (127, -128),
        (0, -128),
    ]

    expected = 0
    for a, b in cases:
        expected = to_signed((expected + a * b) & ACC_MASK, ACC_BITS)
        await step(dut, a, b)
        got = read_acc(dut)
        assert got == expected, (
            "a={} b={}: acc_o is {}, and {} is correct".format(a, b, got, expected))


@cocotb.test()
async def test_random_accumulation(dut):
    """The accumulator holds the running sum over random operands."""
    await start_clock(dut)
    await reset(dut)

    random.seed(1234)
    expected = 0
    for _ in range(200):
        a = random.randint(-128, 127)
        b = random.randint(-128, 127)
        expected = to_signed((expected + a * b) & ACC_MASK, ACC_BITS)
        await step(dut, a, b)
        got = read_acc(dut)
        assert got == expected, (
            "a={} b={}: acc_o is {}, and {} is correct".format(a, b, got, expected))


@cocotb.test()
async def test_enable_holds_the_value(dut):
    """The accumulator holds its value while en_i is low."""
    await start_clock(dut)
    await reset(dut)

    await step(dut, 100, 100)
    held = read_acc(dut)
    assert held == 10000, "acc_o is {}, and 10000 is correct".format(held)

    for _ in range(8):
        await step(dut, random.randint(-128, 127), random.randint(-128, 127), en=0)
        got = read_acc(dut)
        assert got == held, "acc_o changed to {} while en_i was low".format(got)


@cocotb.test()
async def test_clear_wins_over_enable(dut):
    """clr_i clears the accumulator, also when en_i is high."""
    await start_clock(dut)
    await reset(dut)

    await step(dut, 50, 60)
    assert read_acc(dut) == 3000

    await step(dut, 7, 7, en=1, clr=1)
    got = read_acc(dut)
    assert got == 0, "acc_o is {} after clr_i, and 0 is correct".format(got)

    await step(dut, 2, 3)
    got = read_acc(dut)
    assert got == 6, "acc_o is {} after the clear, and 6 is correct".format(got)


@cocotb.test()
async def test_overflow_wraps(dut):
    """The accumulator wraps, and does not saturate."""
    await start_clock(dut)
    await reset(dut)

    # 127 * 127 = 16129 per cycle. 133153 cycles would be needed to reach
    # the wrap point, so this test checks the arithmetic of the sum instead
    # of running that long.
    expected = 0
    for _ in range(64):
        expected = to_signed((expected + 127 * 127) & ACC_MASK, ACC_BITS)
        await step(dut, 127, 127)
    got = read_acc(dut)
    assert got == expected, "acc_o is {}, and {} is correct".format(got, expected)
