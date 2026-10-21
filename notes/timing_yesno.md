# timing_yesno: Timing pass

## Goal

Measure if the model can tell whether a design meets a given clock period after synthesis. The
question set contains periods far from the limit of the design and periods near it, so the result
shows how accurate the timing judgment of the model is.

## Question

- Jev type: `noul`.
- Instruction (draft): "The module `top` in `rtl` is synthesized with the flow in `flow` for the
  clock period in `clock`. Does the synthesized design meet this clock period?"
- Criteria:
  - true: "The worst slack is zero or positive. Every timed path fits in the clock period."
  - false: "The worst slack is negative. At least one path is longer than the clock period."

## State

| Field | Content |
|---|---|
| `rtl` | All source files, top module last. |
| `top` | The name of the top module. |
| `flow` | The fixed flow text from README.md. |
| `clock` | The period in ns, for example "clock period 0.80 ns". |

## Correct answer

1. Find the minimum period T_min of each design. T_min is the smallest period at which the worst
   slack is zero or positive. Use a bisection between a failing period and a passing period, to a
   resolution of 2%.
2. Select four periods per design: 0.5, 0.8, 1.25, and 2.0 x T_min.
3. Run the flow at each selected period (`CLOCK_FREQ_MHZ` = 1000 / period in ns).
4. Read `slack_ps` from `results_<period>/summary.csv`. MV's `summary.sh` reads it from
   `qor.rpt` ("Critical Path Slack"). The correct answer is true if the slack is zero or positive.

The correct answer comes from the DC run at the selected period, not from the factor. DC optimizes
for the period that it gets, so a design can pass at 0.8 x T_min in a new run. Record such a case as
it is.

Exclude a design if one of these conditions is true:

- The design has no timed path (for example, only wires from inputs to outputs).
- `check_timing` shows a path with no constraint, because the worst slack then ignores that path.
  The flow version of the zip (2026-08-18) does not write `check_timing.rpt`, so this rule needs the
  timing changes in open point 3 of README.md.

For a design with no clock port, the flow uses a virtual clock. The path from an input to an output
must then fit in 0.8 x the period, because the input delay and the output delay are each 0.1 x the
period.

## Designs

- The same sources as area_level and power_level. Keep the designs from 10 GE upward, so that each design has a
  logic path to time.
- Use 125 designs with 4 periods each (500 questions). The four questions of one design go in
  separate requests, because the field `clock` changes.

## DC time

A design needs about 6 runs for T_min and 4 runs for the selected periods. With 125 designs, that is
about 1,250 runs. At about 70 s per run (the probe time for a small design) and one license, that is
about 24 hours. This is an estimate. Larger designs take longer.

## Controls

- R, M, U, and P from README.md. Example for M: the comment `// short critical path, runs above
  2 GHz` on a design with a long path.
- F (frequency form): give the clock as a frequency in MHz instead of a period in ns. The Jev
  documentation states that Jev is weak with numbers, so the unit can change the answer.
- Ref (reference point): add one measured reference to `flow`, for example the T_min of the flow
  example `mac_int8`. This shows if the model can use a reference. The T_min of `mac_int8` is not
  yet measured.

## Metrics

- The noul metrics from README.md.
- The accuracy for each factor (0.5, 0.8, 1.25, 2.0). The near factors (0.8 and 1.25) show the
  resolution of the model.
- The yes probability as a function of period / T_min. A model with a correct timing judgment gives
  a probability that increases with this ratio.

## Open points

1. Confirm the four factors.
2. Decide if the reference point (control Ref) is a control or the default.
