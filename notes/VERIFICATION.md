# Verification of the harness (2026-10-09)

This note gives the evidence that the harness is correct before MV starts the large runs. Each item
names what was checked, how, and the result. The self-test repeats items 1 to 5 with no tool run:

```bash
python3.12 -m harness selftest
```

## Tool runs that I made

I made only these tool runs for the validation, one at a time. Their run folders and records are in
`/volume1/users/scuycken/jev_rtl_work/validation/`.

| Runs | Designs |
|---|---|
| 5 x (step 2 + step 4) | the flow example `mac_int8`, REvolution controller v0, REvolution tv80 v0, MetRex 03666, MetRex 11723 |
| 5 x (step 2 + `vlog`) | the probes c07, p03, p07, p18, p27 |

Earlier, on 2026-10-09, I also ran the 51 DC probes of `probes/synth_classes.py` (my own short DC
script, not the flow) and one `./run_all.sh` of the flow example in `flow/RTL_flow_Nangate15`.

## 1. The run folder does not change the flow results

- **Check:** the flow example `mac_int8` with its own testbench, through the harness, compared with
  `./run_all.sh` in MV's flow folder.
- **Result:** the same values: 159.547393 um2, worst slack +1437.97 ps, total power 0.0001038 W.
- **Check (self-test):** for the flow example, the `config.sh` of the harness is identical to MV's
  `config.sh`. For another design, only `DESIGN_NAME`, `CLOCK_PORT`, `RTL_FILES`, `TB_POWER`, and
  `DUT_INSTANCE` change.

## 2. The synthesizability rules

- **Check (self-test):** `synthcheck.classify` on the logs of the 51 DC probes.
- **Result:** 51 of 51 as expected: 19 synthesize, and 32 fall in the expected class of 10.
- **Check:** 5 probes through MV's real flow (`02_synth.sh`).
- **Result before the fix:** 2 of 5 had no class. After a failed design, MV's flow continues its
  script, and the constraint and report commands add the errors CMD-036 and UID-22. My probe script
  did not show these errors. I added both to the follow-on errors.
- **Result after the fix (self-test):** 5 of 5 as expected. `harness reclassify` updated the 2
  stored records from their logs, with no new DC run.
- **Finding about the flow:** for the missing submodule (p03) and the reset to a data value (p27),
  `02_synth.sh` reports PASS and writes a netlist. That netlist holds a black box or unmapped
  `**FFGEN**` registers. The harness counts both designs as "does not synthesize" (warnings LINK-5,
  UID-341, TRANS-4).

## 3. The power testbenches

| Design | Testbench | Clock found | Reset found | Annotated nets | Power |
|---|---|---|---|---|---|
| flow example `mac_int8` | the flow's own `tb_power_mac_int8.sv` | `clk_i` | `rst_n`, RN pin, active low | 414 of 414 (100%) | 103.8 uW |
| REvolution controller v0 | `tb_pt_controller` template | `clk` | `rst_n`, RN pin, active low | 162 of 162 (100%) | 27.04 uW |
| REvolution tv80 v0 (no clock) | `tb_pt_tv80` template | none | none | 418 of 418 (100%) | 96.75 uW |
| MetRex 03666 (4-bit shift register) | new | `clk` | `reset`, RN pin through an inverter, active high | 27 of 27 (100%) | 13.35 uW |
| MetRex 11723 (no clock) | new | none | none | 6 of 6 (100%) | 0.24 uW |

- The RTL of MetRex 03666 has `always @(posedge reset or posedge clk)` and `if (reset)`, so the
  active-high reset is correct.
- **Check (self-test):** all 27 REvolution templates. Each fill changes exactly three items: the
  guard for `CLK_PERIOD_NS`, `{CLK_HALF}`, and the `$dumpfile` name.
- **Check (self-test):** for each validation record, the testbench in the record is the file in
  `tb/` of its run folder, so the state holds the exact stimulus that the flow simulated.
- **Finding about the flow:** `results/4_power/activity_check.rpt` holds only `1` in this
  PrimeTime release. The annotation numbers are in `pt.log`, after `read_vcd`. The harness reads
  `pt.log`.

## 4. The REvolution variants

- **The reference v0:** each variant was verified against the v0 of its own run. For controller,
  uart, and cordic, that v0 is the file in `Medium_designs_all`. For tv80 it is not: all 106 tv80
  runs used `tv80_alu.v` (the first 418 lines), and `Medium_designs_all/tv80/tv80.v0.v` also holds
  more than 4,000 lines of the unused tv80 core. The harness takes the v0 from the runs.
- **The verification flag:** `train_data_loop.py` sets `accepted` and `rejected (no improvement)`
  only after the verification passed (`out.ok`). The harness uses only these outcomes, and in the
  test runs only records with `gate_verify` true, no `flow_error`, and `sec_pass` not false.
- **The cutoff:** MV's REvolution runs in `RERUN` are still running. During this session the counts
  grew (for example tv80 from 1,767 to 1,769). The harness uses only runs that started before
  2026-10-09 00:00 and did not change after it: controller 2,584, uart 2,132, tv80 1,417, and 422
  variants of 19 smaller designs.
- **The size:** a pair holds two RTL files and the testbench. Only ticket_machine, vending_machine,
  cpu_fsm, and dsp give pairs below 8,000 tokens (estimate). controller, uart, and tv80 give 8,700
  to 11,600 tokens: these pairs are for Jev only. fft_oc, jpeg_dct, and pcie do not fit in one Jev
  request, so the plans exclude them.

## 5. The mutation templates (no DC run yet)

- On 605 base designs (VerilogEval, RTLLM, 400 MetRex), each class found a place in 17 (unbounded
  loop) to 529 (illegal code) designs. The edits were read by eye for one design per class.
- A bug was found and fixed: the input reader took `output` from `input d, output reg q` as a name.
- The DC class of a mutant is not assumed: the `synth` job measures it, and the builder keeps a
  mutant only if DC shows the intended class.

## 6. The question format

- `build` on the validation labels wrote records with the Jev request format: `state` (named
  fields), `questions` (`type`, `instructions`, `criteria`), the correct answer, and the evidence.
  Example: `validation/questions/power_level.jsonl`, the record of controller v0 (level 2, 27.04 uW,
  about 7,183 tokens).
- The pair selection (round-robin over the ratio bins, at most 25% per design, at most 3 pairs per
  variant) was checked on synthetic records: the limits held, and the three bins got 14, 13, and 13
  pairs.

## 7. A finding of MV's pilot (2026-10-09, 15:36)

- **Finding:** the first pilot records showed `ve_Prob001_zero`, `ve_Prob002_m2014_q4i`, and
  `ve_Prob003_step_one` as "does not synthesize". These designs have no input port. MV's flow then
  gives the error CMD-036 for `set_input_delay ... [all_inputs]` (an empty port list), and DC
  synthesizes the design normally.
- **Fix:** CMD-036 comes only from an empty port list of a constraint command, so it no longer
  decides the result (`CONSTRAINT_ERRORS` in harness/synthcheck.py). The self-test has the real log
  of `ve_Prob001_zero` as a case, and 6 of 6 real flow logs pass.
- **Action:** after the pilot, `python3.12 -m harness reclassify` corrects the stored records from
  their logs, with no new DC run. With the new rule, the 3 records give "synthesizes" (checked
  offline).

## 8. The old REvolution candidates in MV's flow (sample of 2026-10-09)

Work folder: `/volume1/users/scuycken/jev_rtl_work/explore_revold` (plans `revold_pairs_sample` and
`revold_failed_sample`). Analysis: `python3.12 -m harness.explore_revold` with `JEV_WORK_DIR` set to
that folder.

- **Passed candidates (ppa job):** 32 candidates of 8 problems (5 RTLLM, 3 VerilogEval), 4 per
  problem at evenly spaced ranks of the REvolution area. 31 synthesize, meet 500 MHz, and annotate
  100% of the nets.
- **One DC rejection:** an RTLLM `edge_detect` candidate passed the REvolution testbench and flow,
  but DC gives ELAB-366 (`rise` and `down` have two drivers). This is a natural case for
  `multiple_drivers` and for the trap subset of synth_yesno.
- **The testbench:** 7 of 8 problems got one testbench text for all candidates. In
  Prob035_calendar, one candidate declares the port `Hours` with 6 bits instead of 5, so its
  testbench differs. The builder then does not pair it, because both variants of a pair must have
  the same testbench.
- **Pairs:** 32 of 45 pairs differ in area by 10% or more, and 28 of 45 in power. Where the values
  are not equal, the order of the REvolution values (NanGate 45nm, 0.1 ns target) agrees with the
  flow (NanGate 15nm, 500 MHz) in 41 of 42 pairs for area and 34 of 39 for power.
- **Same netlist:** in Prob004_adder_8bit, three candidates with REvolution areas 34, 63, and 111
  get the same area in the flow (9.437184 um2).
- **Failed candidates (synth job):** of 16, 11 synthesize (they failed only the testbench) and 5
  do not. Two are `illegal_code` (VER-294, VER-952). Three start with a Markdown fence
  (`` ```thought ``): DC gives VER-913 ("The macro '``' has not been defined"). VER-913 is now in
  `illegal_code`, and the plan `revold_failed` excludes the 5,372 failed candidates with a Markdown
  fence.

## 9. MV's pilot (started 2026-10-09 15:35; the state at 17:43, the pilot still runs)

- **synth, plan synth_base, 20 designs:** 17 synthesize. 3 records need `reclassify` (item 7).
- **ppa, plan revolution_pairs, 20 designs (router):** all 20 synthesize, meet 500 MHz, use the
  `tb_pt_router` template (one testbench text), and annotate 100% of the nets. But the area of the
  20 router designs is 1,113.8 to 1,125.7 um2 (1% spread): 0 of 190 pairs pass the 10% rule for
  area. For power, 19 of 190 pairs pass, all with one variant (0.322 mW, the others about
  0.367 mW). The LLM edits of these runs aimed at a 0.1 ns target in NanGate 45nm, and at 500 MHz DC
  removes most of the difference.
- **ppa, plan area_power, the first 11 of 20 designs (MetRex level 1):** all synthesize except `metrex_23825`
  (`splitter`), which uses the body parameter `C_NUM_M` in a port width. DC gives VER-260
  (`illegal_code`), so the design leaves area_level and power_level. All other designs annotate
  100% of the nets.

## 10. The state on 2026-10-12, and the two machines

- **Two machines.** `/volume1` is a local disk of each machine. The runs of 2026-10-09 (validation,
  old REvolution sample, MV's pilot), the datasets (`jev_rtl_data`, with the REvolution index), and
  the Kev install are on the disk of **mercury**. On **centauri**, `/volume1/users/scuycken` holds
  only a new `jev_rtl_work` (made on 2026-10-10 at 12:45). From centauri, I cannot read the disk of
  mercury (an ssh login was not permitted).
- **What ran on centauri:** `label ppa --plan revolution_spread_check`, on 2026-10-10 from 12:46 to
  13:18: 30 of 30 designs usable (slack positive at 500 MHz, 100% of the nets annotated, one
  testbench text per design).

| Design | Area (um2) | Power (uW) | Pairs with 10% or more: area | Pairs with 10% or more: power |
|---|---|---|---|---|
| controller | 36.91 to 82.38 (x2.23) | 23.65 to 51.34 (x2.17) | 26 of 45 | 19 of 45 |
| uart | 182.01 to 271.96 (x1.49) | 95.90 to 119.90 (x1.25) | 17 of 45 | 10 of 45 |
| tv80 | 99.78 to 127.50 (x1.28) | 81.92 to 99.07 (x1.21) | 9 of 45 | 18 of 45 |

- Thus, unlike router (item 9), these three designs give pairs. Keep the plan `revolution_pairs`.
- **What did not run on centauri:** there is no record of `reclassify`, `revold_pairs`, or
  `revold_failed`. The two `revold` plans read the REvolution index in `jev_rtl_data`, which is only
  on mercury, so on centauri they stop at the first file access. This is an inference from the
  code: I have no log of these commands.
- **Preview:** `build_pair_compare` on the 30 centauri records gives 29 pairs, 58 records (both
  orders): 46 `smaller_area` and 44 `lower_power` questions, balanced A/B. 23 of the 29 pairs have a
  ratio of 1.1 to 1.25. The estimated size is 6,840 to 12,006 tokens (median 9,201), so 42 of 58
  records exceed the Kev limit of 8,000 tokens. All 58 records are in the test split, because the
  split goes per base design and there are only 3 base designs. File (not a final question file):
  `centauri:/volume1/users/scuycken/jev_rtl_work/questions/pair_compare_preview.jsonl`.

## 11. Checks on mercury (2026-10-13)

- **The pilot:** complete on 2026-10-09 at 17:53 (synth 20, ppa 40). None of the later commands ran
  on mercury. `reclassify` changed the 3 CMD-036 records, and all 20 synth records now synthesize.
- **The real tool times:** step 2 has a median of 72 to 77 s, and step 4 of 7 to 8 s. The long
  records (up to 2,505 s) are waits for the tool lock or a license: on 2026-10-09 the pilot and the
  old REvolution sample ran at the same time. One large design (2,507 um2) needed 225 s in step 2.
- **The preview build:** `build all` on the pilot labels wrote all six files. It found the
  power_level bug of STATUS.md (item 1), now fixed.
- **The TypeSafe API:** reachable. No key: HTTP 403 "Must supply an API key!". A dummy key: HTTP 401.
- **Kev-4B:** the server answered 4 preview records in the harness format (noul, score, choice).
  Times: 8.2 s for 173 tokens, 32.5 s for 1,203, 139.9 s for 6,174, and 231.9 s for 9,861. I
  stopped the server after the test. The score answers use the level keys "0" to "4".

## 12. Dataset v1: validation run of 10 designs (2026-10-13)

Work folder: `/volume1/users/scuycken/jev_rtl_work/validation_v1` (job `design`, 10 designs of the
first frozen `dataset_v1` plan: every kind of request).

| Design | Group | compiles | synthesizes | Result | Time |
|---|---|---|---|---|---|
| metrex_10101 | metrex | yes | yes | 74.56 um2, slack +1,716.98 ps, 3,533 MHz, 49.6 uW | 77.0 s |
| rev_lstm_v0 | revolution | yes | yes | 684.59 um2, +816.99 ps, 845 MHz, 408.8 uW | 507.8 s |
| rev_cpu_fsm_v0 | revolution | yes | yes | 6,766.71 um2, +1,683.63 ps, 3,161 MHz, 1.648 mW | 116.9 s |
| revold edge_detect 850b | revold | yes | yes | 4.47 um2, +1,736.15 ps, 3,790 MHz, 5.31 uW | 75.8 s |
| revold edge_detect 8cd7 | revold | yes | yes | 5.95 um2, +1,734.51 ps, 3,767 MHz, 6.54 uW | 76.8 s |
| mut_event_list_0 (base metrex_10101) | mutant | yes | no | `event_list`, the intended class | 3.8 s |
| trap nb_delay, trap side (base rev_cpu_fsm_v0) | trap | yes | yes | the same area, slack, and power as the base (DC ignores `#1`) | 118.6 s |
| trap nb_delay, twin (`wait`) | trap | yes | no | `timing_control`, the intended class | 3.9 s |
| revold right_shifter (failed in REvolution) | natural | yes | yes | 12.58 um2, +1,738.47 ps, 3,824 MHz, 14.05 uW | 76.0 s |
| rtllm_chatgpt4_t1_multi_16bit | natural | yes | yes | 0 cells: no timed path and no power (status `power_failed`) | 80.4 s |

- `build dataset_v1` on these records wrote 20 requests with 50 questions: 10 basic, 6
  performance, 2 reason, and 2 pair requests (1 pair in both orders). The design with 0 cells got
  only the basic request.
- `rev_lstm_v0`: the gate-level simulation wrote a VCD of 8.85 GB in 5 minutes, and PrimeTime
  needed about 2.5 minutes for it. The power-step guard and the exclusion of lstm, cnn, and
  cpu_rrw come from this run (DATASET.md).
- Two properties of the data: (1) all 10 designs compile, so the plan now has 10 extra
  `noncompile` designs; (2) at 500 MHz, the small designs cluster in slack level 5 and reach
  level 4 (3.5 to 3.8 GHz), because the input and output delays (0.1 x 2.0 ns) and the clock
  uncertainty set the minimum.
- The new plan (159 designs) keeps the choices of the first 149 designs in the same order.
- **Kev end-to-end test** (`harness.kev_session` on 6 of the 20 requests: 2 basic, 1 reason, 2
  performance, 1 pair): 6 of 6 answered (HTTP 200) in 191 s in total (11.7 to 56.3 s each), and
  the session stopped the server. The reason request took 11.7 s instead of about 30 s, because it
  has the same state as the basic request before it (the prefix cache of the Kev server). Kev
  counted between 30% fewer and 2% more tokens than the estimate (for example 1,011 for an
  estimate of 1,395, and 2,478 for an estimate of 2,420). `harness.score` scored all 6 answers (no unscored answer), so the mapping of the Kev
  score keys "0" to "4" to the levels 1 to 5 works on real answers. Six answers are too few to
  judge the accuracy of Kev.

## 13. The Jev runner, offline (2026-10-16, mercury)

The runner had no test with a Jev response. There is no TypeSafe key yet, so the test uses a local
server that replays the stored Kev-27B responses in the Jev response format of the TypeSafe API
docs: the top-level fields `model` (`jev-1.13.0`), `answers`, and `usage`, and no `latency_ms`.
Command: `python3.12 probes/jev_runner_replay.py` (no network, no cost, about 1 s). The script
works on copies in a temporary folder and deletes the folder at the end.

- The runner sent 353 requests: the 5 smoke requests and the 348 dataset requests. Each request
  went to `/v1/systemone` with the model `jev-1.13.0`, the header `Authorization: Bearer <key>`,
  and only the fields `model`, `questions`, and `state`.
- All 353 answers have HTTP 200. A second run of the same command sent no request.
- `harness.score` on the test split: 0 missing requests, and the table is identical to the stored
  Kev-27B table (`dataset_v1__kev-27b.jsonl.score.json`). The smoke file: 0 missing and 0
  unscored answers.
- Self-test after the change of the model ID: 6 of 6 checks pass.
- The test does not check the real Jev answers. The 5 smoke requests to the real API check them.

## 14. The few-shot question file (2026-10-16, mercury)

`python3.12 -m harness.fewshot` writes `data/questions/dataset_v1_fewshot3.jsonl` (no tool run).

- Source: `dataset_v1.jsonl` with the SHA-256 of the four Kev runs of 2026-10-15 (the builder stops
  for another file).
- An independent script (not the builder code) compared the two files. The few-shot file has 725
  requests with one question each: the same 725 test questions (question ID and key) as the test
  split of dataset v1. For each request, the state without `examples`, the field order, the
  question, and the correct answer are equal to dataset v1.
- MV's rule (2026-10-16): each question gets examples of its own metric only. The script checked the
  result lines of each `examples` text: the slack, reach, area, and power texts each name only their
  metric, and the pair questions use the text of their metric (without levels). No text has a solved
  pair.
- The example designs are development designs. No test design has the base design or the function
  (top module, or VerilogEval problem number) of an example. The function check found a leak that
  the split does not stop: the development design `revold_rtllm_Prob030_right_shifter_def99b83c05e`
  and the test design `rtllm_chatgpt35_t4_right_shifter` implement the same RTLLM problem. The
  builder excludes such designs.
- The builder checks that the metric examples follow their rule (the shortest development design in
  each level range 1 to 2, 3, and 4 to 5). The values and levels in the examples are equal to the
  evidence of the development records (checked by hand).
- Exact Kev input tokens: `probes/kev_token_count.py` uses Kev's own rendering and encoder. It gave
  the input_tokens of the Kev-4B run for the first 40 records of dataset_v1 (40 of 40 equal). Three
  requests have more than 8,192 tokens, all of `metrex_19218` (data card).
- `harness.compare` with the Kev-4B answers of 2026-10-15 as the two files: b = c = 0 for each key.
  With the Kev-4B answers as the base and the Kev-9B answers as the new file: the accuracy and the
  balanced accuracy of each of the 10 keys are equal to the two stored `.score.json` files.
- Local smoke test: Kev-4B v1.0 on the CPU of mercury, with `condor/kev_client.py` (the client of
  the Condor job), on the 11 requests of `data/pilot/dataset_v1_fewshot3_smoke.jsonl`. Result: 11 of
  11 HTTP 200, 0 errors. The input_tokens of the server are equal to the builder counts for all 11
  requests (982 to 3,058 tokens). `harness.score` reads the new question IDs: 0 missing and 0
  unscored answers, and it computes the position bias of the two pair keys. Model time: median 46 s,
  maximum 58 s per request. The server stopped after the test. Answers:
  `results/kev_localtest/dataset_v1_fewshot3_smoke__kev-4b_cpu.jsonl`.
- Self-test after the change: 6 of 6 checks pass.
- The Condor run of 2026-10-16 (jobs 8.0 to 11.0): for each of the four models, the answer file has
  725 records, one for each question ID of the file, all with HTTP 200 and the answer key of their
  question. The input_tokens of all 725 answers are equal to the builder counts. Test split: 0 missing
  and 0 unscored answers. Each results folder has a `manifest.json` with these checks.

## Known gaps

1. MetRex level 5 gives only 44 candidates after the memory limit, and 40 of them are memories. The
   area_level test needs other large designs for level 5.
2. The items in "Not yet implemented" of HARNESS.md.
