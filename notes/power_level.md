# power_level: Power level

## Goal

Measure if the model puts a design in the correct power level from the RTL and the power testbench.
The levels are decades of microwatt, so the question does not need a precise number.

## Question

- Jev type: `score`, 5 levels.
- Instruction (draft): "Estimate the total power (dynamic plus leakage) of the module `top` in `rtl`
  after synthesis with the flow in `flow` at the clock in `clock`, with the stimulus of the power
  testbench in `tb_power`. Select the power level."
- Criteria, from low to high (draft, see the open points):
  1. "Below 10 uW."
  2. "10 uW to 100 uW."
  3. "100 uW to 1 mW."
  4. "1 mW to 10 mW."
  5. "10 mW or more."

## State

| Field | Content |
|---|---|
| `rtl` | All source files, top module last. |
| `top` | The name of the top module. |
| `flow` | The fixed flow text from README.md. |
| `clock` | "500 MHz (clock period 2.0 ns)" |
| `tb_power` | The power testbench. It is the exact file that the flow simulates. |

## The power testbench

- REvolution designs: the template `tb_pt_<design>.sv` of the design. The harness fills its
  placeholders: the half clock period becomes `` `CLK_PERIOD_NS / 2.0 ``, and the VCD file becomes
  `power.vcd`. The instance name of the template becomes `DUT_INSTANCE`.
- Designs without a power testbench (MetRex, VerilogEval, RTLLM): the harness writes one in the same
  style as `tb_pt`. It uses the same seed (`32'hC0DE0042`), 8 reset cycles, 16 warm-up cycles, 4,000
  measured cycles, a new random value on each data input in every cycle, and a random reset in about
  1 of 32 cycles.
- The harness reads the ports from the netlist of step 2, not from the RTL. The clock port is the
  input that connects to the `CLK` pins of the flip-flops. The reset port and its polarity come from
  the port name. The testbench is in the state, so the model sees the same stimulus as the flow, also
  if the harness selects a wrong reset port.

## Correct answer

1. Run step 2 of the flow at 500 MHz.
2. Write the power testbench into `tb/` of the run folder.
3. Run step 4 of the flow (gate-level simulation in QuestaSim, then PrimeTime).
4. Read `total_power_w` from `results/summary.csv`. Select the level from the criteria.

Exclude a design if one of these conditions is true:

- The worst slack at 500 MHz is negative.
- The VCD annotates less than 95% of the nets. The number is in `results/4_power/pt.log`, after
  `read_vcd` ("Number of annotated nets = ..."). The flow also writes `activity_check.rpt`, but in
  this PrimeTime release that file holds only `1`.
- The power is within +/-10% of a level edge.
- The design has no clock.

## Reference point (measured in this flow)

The flow example `mac_int8` has a total power of 0.1038 mW at 500 MHz with its own power testbench
(`tb_power_mac_int8.sv`). It is near the edge of levels 2 and 3, so the edges can need a change (see
the open points).

## Designs

- The same sources as area_level. A design can be in area_level and in power_level.
- Make 100 questions per level.

## Analysis

- Power and area are related. Compare each power_level answer with the area_level answer of the
  same design. If the model is correct in power_level only where it is correct in area_level, it
  uses the area and not the activity.
- Add a subset of designs that have the same area level but a different activity, for example a
  design with an enable that is mostly off and a design without it.

## Controls

- R, M, U, and P from README.md. Example for M: the comment `// low-power block, mostly idle` on a
  design that toggles in every cycle.
- K (choice form) as in area_level.
- T (no testbench): on a 10% sample, ask the question without `tb_power`. This shows if the model
  uses the testbench.

## Metrics

- The score metrics from README.md.
- The fraction of designs with the same level error in area_level and in power_level.

## Open points

1. Fix the level edges after a pilot of 50 designs. Keep the edges in decades, but move them if one
   level has too few designs or too many designs near an edge. Fix the edges before the test set.
