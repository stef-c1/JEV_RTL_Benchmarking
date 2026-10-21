# pair_compare: Cost comparison of two variants

## Goal

Measure if the model can tell which of two variants of the same function is better in area, power,
maximum clock frequency, and energy per operation. A comparison does not need a number, so it removes
the numeric weak point of Jev from the answer. This test is the only test with energy per operation,
because the two variants share one definition of an operation.

## Questions

All questions use the Jev type `choice` with two options: `A` ("the design in `rtl_a`") and `B`
("the design in `rtl_b`"). One request holds all questions for one pair.

| Key | Instruction (draft) | Pair source |
|---|---|---|
| `smaller_area` | "Which variant has the smaller total cell area after synthesis with the flow in `flow` at the clock in `clock`?" | REvolution, Orchestrator |
| `lower_power` | "Which variant has the lower total power after synthesis with the flow in `flow` at the clock in `clock`, with the stimulus of the power testbench in `tb_power`?" | REvolution, Orchestrator |
| `higher_fmax` | "Which variant reaches the higher maximum clock frequency after synthesis with the flow in `flow`?" | Orchestrator |
| `less_energy` | "Which variant uses less energy per operation for the stimulus of the power testbench in `tb_power`? `operation` defines one operation." | Orchestrator |

## State

| Field | Content |
|---|---|
| `rtl_a`, `rtl_b` | All source files of each variant, top module last. |
| `top` | The name of the top module. Both variants have the same top module and the same ports. |
| `flow` | The fixed flow text from README.md. |
| `clock` | The common clock: "500 MHz (clock period 2.0 ns)". |
| `tb_power` | The power testbench. It is the same file for both variants, and it is the exact file that the flow simulates. |
| `operation` | Only for `less_energy`: the definition of one operation, for example "one signed 8-bit multiply-accumulate". |

## Correct answers

1. Run the flow on both variants at 500 MHz (steps 2 and 4), with the same power testbench.
2. Drop the pair if one variant has a negative worst slack at 500 MHz.
3. Get the values of each variant from `results/summary.csv` of its run folder:
   - Area: `area_um2`.
   - Power: `total_power_w`.
   - Maximum clock frequency: 1 / T_min, with T_min as in timing_yesno.
   - Energy per operation: total power x run time of the stimulus / number of operations in the
     stimulus. The run time is the number of measured cycles x the clock period.
4. The correct answer of a question is the variant with the better value.

Keep a question only if the two values differ by 10% or more. Record the ratio of the two values for
the analysis.

Energy per operation gives a different answer from power only if the two variants need a different
number of cycles for the stimulus. The Orchestrator family has this case, for example a 4 x 4 array
and a larger array of the same processing element. The REvolution variants of one design all run the
same testbench for the same number of cycles, so they get no `less_energy` question.

## Pairs

- Both variants have the same top module, the same ports, and the same function.
- REvolution: the loop verified each variant against v0 (see DATA.md). Two variants of one design are
  thus equal in function to v0 and to each other, within the limits of that verification.
- Orchestrator: all 54 variants passed the same acceptance testbench.
- Ask each pair in both orders (A/B and B/A). This is the built-in control for the option order.
- Make 500 questions per key: 250 pairs that pass the 10% rule, each in both orders.

## Result of the pilot and of the old REvolution sample (2026-10-09)

- The 20 router designs of the new REvolution runs differ by only 1% in area at 500 MHz, so they
  give no area pair (VERIFICATION.md, item 9).
- The independent candidates of the old REvolution runs (ASP-DAC 2026) differ much more: in a
  sample of 8 problems, 32 of 45 pairs pass the 10% rule for area, and 28 of 45 for power
  (VERIFICATION.md, item 8). They are small, so their pairs also fit the Kev limit.
- Thus the old REvolution candidates (plan `revold_pairs`, one group per problem) are the main pair
  source. The new REvolution variants stay only for the designs where the labels show a spread.

## Pair selection from REvolution

- Use the 3 designs with thousands of variants (controller, uart, tv80) and the 23 designs of the
  training corpus (about 20 variants each).
- Many variants differ only a little. Select candidate pairs with the earlier REvolution values
  (NanGate 45nm) so that the ratios spread over 1.1 to 1.25, 1.25 to 2, and 2 or more. Then label the
  pairs with the flow, and keep a pair only if the flow ratio passes the 10% rule.
- Take at most 25% of the pairs from one design. Then no single design decides the result.
- Use each variant in at most 3 pairs.

## Pair size

A pair holds two RTL files and the testbench. Only ticket_machine, vending_machine, cpu_fsm, and dsp
give pairs below 8,000 tokens (the Kev limit, estimate). controller, uart, and tv80 give 8,700 to
11,600 tokens, so their pairs are for Jev only. fft_oc, jpeg_dct, and pcie do not fit in one Jev
request (30,000 tokens with a margin), and the plans exclude them. Thus the Kev result covers only
the four small designs.

## Pair sources that are not REvolution

- Orchestrator `mac_array_int8` results: 54 variants, which give 1,431 possible pairs before the 10%
  rule. The stored results use 12 different clock periods (0.8967 ns to 5.6889 ns), so synthesize all
  variants again at 500 MHz. The RTL of one variant has 4,089 to 14,603 characters, so a pair can
  exceed the limit of 8,000 tokens. Count the tokens, and put a pair above the limit in a Jev-only
  subset.
- Parameter variants (for example a width of 8 and of 16). The answer is then often "the smaller
  parameter is smaller". Mark them and report them separately.

## Controls

- R, M, and P from README.md. Example for M: the comment `// area-optimized version` on the larger
  variant.
- O is built in (both orders).
- S (separate requests): on a 10% sample, ask each question in its own request. This shows if the
  questions in one request change each other.
- T (no testbench): on a 10% sample, ask `lower_power` without `tb_power`. This shows if the model
  uses the testbench.

## Metrics

- The choice metrics from README.md, for each key.
- The accuracy for each ratio range: 1.1 to 1.25, 1.25 to 2, and 2 or more.
- The position bias: the fraction of pairs where the model selects the same position (A or B) in
  both orders.
- The transitivity in one design family: if the model selects A over B and B over C, it must also
  select A over C. Report the fraction of triples that break this rule.
- The results separately for each design.

## Open points

1. The power testbench of the Orchestrator family. Its harness measured power with a dense and a
   sparse workload. I have not yet located the testbench file for the flow.
