# area_level: Area level

## Goal

Measure if the model puts a design in the correct area level from the RTL only. The levels are
decades of gate equivalents (GE), so the question does not need a precise number.

## Question

- Jev type: `score`, 5 levels.
- Instruction (draft): "Estimate the total cell area of the module `top` in `rtl` after synthesis
  with the flow in `flow` at the clock in `clock`. 1 GE is the area of one two-input NAND gate.
  Select the area level."
- Criteria, from low to high:
  1. "Below 100 GE."
  2. "100 GE to 1,000 GE."
  3. "1,000 GE to 10,000 GE."
  4. "10,000 GE to 100,000 GE."
  5. "100,000 GE or more."

## State

| Field | Content |
|---|---|
| `rtl` | All source files, top module last. |
| `top` | The name of the top module. |
| `flow` | The fixed flow text from README.md. |
| `clock` | "500 MHz (clock period 2.0 ns)" |

## Correct answer

1. Run the flow at 500 MHz (`CLOCK_FREQ_MHZ=500`). This is the default clock of the flow.
2. Read "Total cell area" (um2) from `results/2_synth/area.rpt`.
3. Divide the area by 0.196608 um2 to get GE. Select the level from the criteria.

Exclude a design if one of these conditions is true:

- The worst slack at 500 MHz is negative. DC then enlarges the cells on the failing paths, so the
  area depends on the clock and not only on the logic.
- The area is 0 (the design has no cells).
- The area is within +/-10% of a level edge (for example 90 GE to 110 GE). A small change in the
  synthesis can then move the design to the next level.

## Reference points (measured in this flow)

| Design | Area | GE | Level |
|---|---|---|---|
| 8-bit accumulator with asynchronous reset (probe `c00_clean`, 1 GHz) | 19.02 um2 | 97 | 1 (near the edge) |
| Flow example `mac_int8` (signed 8-bit multiplier, 32-bit accumulator, 500 MHz) | 159.55 um2 | 811 | 2 |
| Orchestrator `mac_array_int8`, run `loop_repair` (4 x 4 array) | 11,446.78 um2 | 58,222 | 4 |
| 54 Orchestrator `mac_array_int8` results | 11,013.73 um2 to 39,353.10 um2 | 56,019 to 200,160 | 4 and 5 |

The Orchestrator areas come from each run at its own clock, not at 500 MHz. Synthesize them again at
500 MHz before use.

## Designs

- VerilogEval reference solutions and RTLLM verified designs. I expect most of them in levels 1 to 3.
  This is an estimate, not a measurement.
- Orchestrator results for levels 4 and 5. Only 6 of the 54 results have 100,000 GE or more.
- REvolution v0 designs and MetRex designs, synthesized again in this flow.
- Parameter variants: the same RTL with other parameter values (for example a larger array or a
  deeper FIFO). They fill levels 4 and 5. Mark them, because the model must read a number to answer.
- Make 100 questions per level. Level 5 is the main gap.
- Limit register-array memories to 25% of each level. In MetRex, 96% of the level 5 candidates and
  64% of the level 4 candidates are such memories (see DATA.md).

## Controls

- R, M, U, and P from README.md. Example for M: the comment `// small 4-entry buffer` on a
  64-entry FIFO.
- A (anchors): add the three measured reference points above to the level descriptions.
- K (choice form): ask the same 5 levels as a `choice` question with the options in random order.
  This shows if the `score` type adds a bias toward the middle levels (arXiv 2609.38827).
- O does not apply, because the levels of a `score` question must be in order.

## Metrics

- The score metrics from README.md.
- The results separately for each source and for the parameter variants.

## Open points

1. Confirm the clock of 500 MHz.
2. Confirm the decade levels in GE.
