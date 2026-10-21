# JEV_RTL test notes

This folder defines the tests of the JEV_RTL study. The study measures how well Jev (TypeSafe AI) and
similar decision models answer questions about RTL. Each test has its own file. This file gives the
scope, the list of tests, and the rules that apply to all tests.

## Scope

MV set the scope on 2026-10-09. The study covers two areas only:

1. Synthesizability: does the design synthesize, and if not, why not.
2. Hardware cost: area, power, timing, and energy per operation.

The other question groups of the first plan (lint, logic analysis, agent-loop decisions) are out of
scope for now.

## Dataset

[DATASET.md](DATASET.md) defines dataset v1 (MV, 2026-10-13): one test is one RTL design, and each
design gets a bundle of questions (compilation, synthesizability and the reason, slack, reachable
clock frequency, area, power, and pair comparisons). The six notes below define the question types.
Their sizes, balancing rules, and controls are from the earlier plan and do not apply to v1.

## Question types

| Test | File | Question to the model | Jev type | Correct answer from |
|---|---|---|---|---|
| synth_yesno | [synth_yesno.md](synth_yesno.md) | Does Design Compiler synthesize this design? | noul | DC log |
| synth_reason | [synth_reason.md](synth_reason.md) | Why does Design Compiler not synthesize it? (10 classes) | choice | DC message ID |
| area_level | [area_level.md](area_level.md) | Which area level does the design have? (5 levels) | score | DC `report_area` |
| power_level | [power_level.md](power_level.md) | Which power level does the design have? (5 levels) | score | PrimeTime `report_power` |
| timing_yesno | [timing_yesno.md](timing_yesno.md) | Does the design meet the clock period T? | noul | DC worst slack |
| pair_compare | [pair_compare.md](pair_compare.md) | Which of two variants is better in area, power, maximum clock, or energy per operation? | choice | DC and PrimeTime |

Energy per operation is in pair_compare only. Energy per operation needs a defined operation. Two
variants of the same function have the same operation, but two unrelated designs do not.

The test names state the metric and the answer type. The same name is the file name and the value of
the field `test` in the data.

## Harness

[HARNESS.md](HARNESS.md) describes the harness that makes the questions, and the commands for the
label runs. [VERIFICATION.md](VERIFICATION.md) gives the evidence that the harness is correct.
[STATUS.md](STATUS.md) gives the state and the remaining work.

## Who runs what

- I (Claude) write the harness and test it with a small number of tool runs. I report each of these
  runs.
- I do not start the large labeling runs. First I show MV the evidence that the harness is correct.
  Then MV starts each large run with the command that I give.

## Rules for all tests

### The flow

- All correct answers come from one flow: `JEV_RTL/flow/RTL_flow_Nangate15`. MV gave this flow as
  `RTL_flow_Nangate15.zip` on 2026-10-09. Its files have the date 2026-08-18.
- On 2026-10-09, `./00_check.sh` passed in this folder, and `./run_all.sh` on the example `mac_int8`
  gave 159.547393 um2, a worst slack of +1437.97 ps at 500 MHz, and 0.1038 mW.
- Tools: Design Compiler U-2022.12-SP2 (`compile_ultra -gate_clock`), PrimeTime U-2022.12-SP2, and
  QuestaSim 2022.4.
- Library: NanGate 15nm Open Cell Library, typical corner, 0.8 V, 25 C.
- Constraints (flow defaults): input and output delay of 0.1 x the clock period (setup check only,
  `-max`), setup clock uncertainty 0.05 ns, maximum transition 0.25 ns, maximum fanout 32, no output
  load, no driving cell.
- The copy in `Synthesis_scripts/RTL_flow_FreePDK15` is newer (2026-09-28). It has the same library
  file and the same defaults, but three timing changes: it times the reset recovery and removal
  checks, it applies the input and output delay also to the hold check, and it writes
  `check_timing.rpt`. See the open points.
- Gate equivalent (GE): 1 GE is the area of `NAND2_X1`, which is 0.196608 um2 in this library.
- Do not change the flow settings during the study. If a setting must change, rerun all tests.

### The DC license

- The DC licenses are shared with other users. Run one DC job at a time.
- On 2026-10-09, four parallel DC jobs got the error "All 'Design-Compiler' licenses are in use"
  (SEC-50). If DC reports SEC-50, wait and try again. Do not record SEC-50 as a design result.
- A DC run of a small probe design took about 70 s on mercury (two probes, with `vlog`, in 2 min 25 s).
  Larger designs take longer.

### The request to the model

- Send one request per design, or one request per design pair in pair_compare.
- The state has named fields. All tests use `rtl` (all source files, top module last) and `top` (the
  name of the top module). Each test file lists its other fields.
- The power questions (power_level, and `lower_power` in pair_compare) also put the power testbench
  in the state, in the field `tb_power`. The power value comes from this testbench, so the model gets
  the same stimulus that the flow uses.
- The hardware-cost tests also use the field `flow` with this fixed text: "Synopsys Design Compiler
  (compile_ultra), NanGate 15nm Open Cell Library, typical corner 0.8 V and 25 C, input and output
  delay 10% of the clock period, clock uncertainty 50 ps."
- Each test file gives a draft of the instruction. Tune the wording on the development set only.
  Then freeze it for the test set.
- The state plus the longest question must stay below 8,000 tokens. The Kev authors validated Kev-0.8B,
  Kev-4B, and Kev-9B up to 8,192 tokens. Jev accepts 32k tokens for the state plus the longest
  question.

### The models

1. Jev 1.13 through the TypeSafe API, with the model ID `jev-1.13.0`. MV decided on 2026-10-16: use only
   the stable release, and send the requests from mercury with `harness.runner`, not from Condor. The
   request names the version, because the alias `jev-latest` moves to the next stable release. The
   preview release `jev-1.14.0` (alias `jev-preview`, 2026-10-14) is not in the study.
2. Kev-0.8B, Kev-4B, and Kev-9B, run locally with the same API. Kev-4B v1.0 is installed on mercury in
   `/volume1/users/scuycken/kev` (installed on 2026-10-09). Mercury has no GPU, so Kev runs on the
   CPU. A request with 101 tokens took 6.9 s. The time for an RTL state of several thousand tokens is
   not yet measured.
3. Qwen3.5-4B with the LLM-as-Jev method (the base model of Kev-4B).
4. One or two large commercial LLMs, with no tools (no commands, no files, no web).
5. The majority answer and a random answer, as the lower reference.

### Size and split

- Dataset v1 has about 150 designs (DATASET.md). There is no target of questions per type.
- Put all questions from one base design in the same set (20% development, 80% test). Then no design
  is in both sets.

### Controls

Dataset v1 has no controls, except the two orders of each pair. The controls below are for a later
version. Each test file lists the controls that it uses. A control is a variant of each question.

| Code | Variant | What it shows |
|---|---|---|
| R | Rename all signals and modules to neutral names (`s1`, `m1`), and delete all comments. | Does the model use the names instead of the logic? |
| M | Add one misleading comment that suggests the wrong answer. | Does a normal comment change the answer? |
| U | Add unrelated modules to the file. Only `top` counts. | Does unrelated text decrease the accuracy? |
| O | Change the order of the options. | Does the answer depend on the position of an option? |
| P | Write the instruction with different words. | Does the answer depend on the wording? |

- A variant must keep the correct answer. Rerun the tool on all R and U variants of a 10% sample. If
  the result changes for one sample, rerun the tool on all variants.
- A misleading comment must not contain the words `synopsys`, `synthesis`, `pragma`, or
  `translate`, because DC reads some comments with these words as commands.

### Metrics

- noul: accuracy at the threshold 0.5, balanced accuracy, AUROC, Brier score, and calibration error
  (10 equal bins) with a reliability plot.
- choice: accuracy, balanced accuracy, the confusion matrix, and the calibration error of
  `confidence`.
- score: accuracy of the exact level, mean absolute error in levels, Spearman rank correlation, and
  the number of answers per level compared with the correct number per level.
- Controls: the fraction of answers that change from the original question.
- Cost in USD per 1,000 questions, and the time per request.
- Compare two models on the same questions with a paired test (McNemar).

### Storage

- Keep the questions of one test in one JSONL file, and the answers of one model run in one JSONL
  file. The home folder has an inode quota, so do not write one file per question.
- Keep the run folders and the tool logs outside the home folder, in
  `/volume1/users/scuycken/jev_rtl_work` on mercury (local disk, no quota).
- One question record holds: `test`, `question_id`, `design_id`, `base_design_id`, `source`,
  `variant`, `split`, `state`, `question`, `correct_answer`, and `evidence` (the tool, the report
  path, the value, and the message IDs).
- One answer record holds: `question_id`, `model`, `answer`, `probabilities`, `confidence`,
  `input_tokens`, and `latency_ms`.

### Design sources

[DATA.md](DATA.md) gives the datasets, the generated variants, and which test uses which source.

### Open points for all tests

1. A TypeSafe API key. I have not yet tested if this machine can connect to `api.typesafe.ai`.
2. The flow version. The 2026-08-18 version does not time the reset recovery and removal checks.
   timing_yesno uses the worst slack, so a reset path can change its correct answer. Either keep the
   version of the zip, or add the three timing changes of the 2026-09-28 copy before the first labels.
