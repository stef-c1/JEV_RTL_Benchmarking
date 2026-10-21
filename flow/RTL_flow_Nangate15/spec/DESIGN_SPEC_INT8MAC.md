# Design specification: mac_int8

The example design of the flow. `config.sh` points at it, so `./run_all.sh`
runs it. Write your own specification the same way, in this file or next to
it.

## 1. Function

The design multiplies two signed 8-bit operands and adds the product to a
32-bit signed accumulator. It accumulates on a rising clock edge when the
enable is high, and holds the accumulator when the enable is low.

## 2. Structure

| Module | File | Function |
| --- | --- | --- |
| `mac_int8` | `rtl/mac_int8.v` | The top module. It connects the multiplier to the accumulator. |
| `mult_signed8` | `rtl/mult_signed8.v` | Multiplies two signed 8-bit operands into a signed 16-bit product. |
| `acc_signed32` | `rtl/acc_signed32.v` | Adds the product to a signed 32-bit sum, with an enable and a synchronous clear. |

## 3. Interface

| Port | Direction | Width | Description |
| --- | --- | --- | --- |
| `clk_i` | input | 1 | Clock. Every register is on the rising edge. |
| `rst_n` | input | 1 | Reset, active low, asynchronous. It clears `acc_o`. |
| `en_i` | input | 1 | Accumulate when high, hold when low. |
| `clr_i` | input | 1 | Clear the accumulator on the next rising edge. It wins over `en_i`. |
| `a_i` | input | 8 | First operand, two's complement, -128 to 127. |
| `b_i` | input | 8 | Second operand, two's complement, -128 to 127. |
| `acc_o` | output | 32 | Accumulator, two's complement. It wraps on overflow. |

## 4. Timing

| Item | Value |
| --- | --- |
| Target frequency | 500 MHz |
| Latency | 1 clock cycle from the operands to `acc_o` |
| Throughput | 1 multiply-accumulate per clock cycle |
| Reset | Hold `rst_n` low for at least 2 clock cycles |

## 5. Constraints

| Item | Value |
| --- | --- |
| Technology | NanGate 15nm Open Cell Library, typical corner (0.8 V, 25 C) |
| Maximum transition | 0.250 ns |
| Maximum fanout | 32 |
| Clock uncertainty | 0.05 ns setup, 0.025 ns hold |

## 6. Verification plan

Every check is in `tb/test_mac_int8.py`, and `tb/tb_verify_mac_int8.sv`
repeats it in SystemVerilog.

| Check | Test |
| --- | --- |
| The reset clears the accumulator | `test_reset_clears_accumulator` |
| The corner products are correct, including -128 x -128 and -128 x 127 | `test_directed_products` |
| The accumulator holds the running sum over 200 random operand pairs | `test_random_accumulation` |
| The accumulator holds its value while `en_i` is low | `test_enable_holds_the_value` |
| `clr_i` clears the accumulator, also when `en_i` is high | `test_clear_wins_over_enable` |
| The accumulator wraps, and does not saturate | `test_overflow_wraps` |

## 7. Power workload

`tb/tb_power_mac_int8.sv` applies 256 cycles of random signed operands, 64
cycles of a sign-alternating ramp, one clear, and 64 idle cycles with the
enable low.

## 8. Open points

The accumulator wraps on overflow. A design that must saturate needs a
different specification and a further test.
