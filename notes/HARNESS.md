# The harness

The harness in `JEV_RTL/harness/` turns designs into questions with correct answers. Every correct
answer comes from MV's flow in `flow/RTL_flow_Nangate15`. The harness never changes a file of that
flow.

Run every command from the folder `JEV_RTL` with Python 3.12. The harness uses only the Python
standard library.

## How one design runs

1. The harness makes a run folder for the design in `/volume1/users/scuycken/jev_rtl_work/runs/`.
   The folder has links to the scripts, `scripts/`, `tech/`, and `tools/` of MV's flow, and its own
   `config.sh`, `rtl/`, `tb/`, and `results/`.
2. The `config.sh` of the run folder is MV's `config.sh` with five lines replaced: `DESIGN_NAME`,
   `CLOCK_PORT`, `RTL_FILES`, `TB_POWER`, and `DUT_INSTANCE`. All other settings are MV's.
3. The harness runs MV's step scripts (`02_synth.sh`, `04_power.sh`) in the run folder, with stdin
   from `/dev/null`, and then MV's `summary.sh`. It reads the numbers from `results/summary.csv`.
4. Only one tool runs at a time (a lock file, shared by all harness processes). If a tool reports
   that no license is free (SEC-50), the harness waits 60 s and runs the step again, up to 30 times.

## The label jobs

| Job | Used by | What it does for one design |
|---|---|---|
| `synth` | synth_yesno, synth_reason | Step 2 with `CLOCK_PORT=""`, then `vlog -sv` on the RTL. `synthcheck.classify` gives "synthesizes" and the class. |
| `ppa` | area_level, power_level, pair_compare | Step 2 at 500 MHz. The clock is checked against the `CLK` pins of the netlist. Then the power testbench and step 4. |
| `period` | timing_yesno | A bisection for T_min (step 2 at several periods, 2% resolution), then step 2 at 0.5, 0.8, 1.25, and 2.0 x T_min. |

- A job writes one JSON record per design to `jev_rtl_work/labels/<job>.jsonl`. A design with a
  record is skipped, so a stopped job continues where it stopped.
- The power testbench: for a REvolution design, its `tb_pt` template with three changes (the clock
  guard, `{CLK_HALF}`, and the VCD name). For another design, a new testbench in the same style. The
  harness reads its ports, the clock, and the asynchronous reset from the netlist of step 2.
- The `synth` job uses `CLOCK_PORT=""`, because synthesizability does not depend on the clock
  constraint, and a wrong clock guess would add a false error.

## The plans

A plan is the list of designs for one job. The first `plan` or `label` call freezes the plan in
`jev_rtl_work/plans/<plan>.jsonl`, with the full RTL of each design. Later calls read that file.

| Plan | Job | Designs | Needs first |
|---|---|---|---|
| `synth_base` | synth | 531: VerilogEval 156, RTLLM 50, REvolution v0 25, MetRex 300 | none |
| `rtllm_llm` | synth | 290 RTLLM files of GPT-3.5 and GPT-4 | none |
| `synth_mutants` | synth | up to 80 mutants per class (800) | `synth_base` complete |
| `synth_traps` | synth | up to 60 trap pairs (120 designs) | `synth_base` complete |
| `revolution_pairs` | ppa | 526: v0 and variants of 18 REvolution designs | none |
| `area_power` | ppa | 914: MetRex 684, VerilogEval 156, RTLLM 50, REvolution v0 24 | none |
| `timing` | period | 160 designs from the `area_power` labels, each at least 10 GE | `area_power` complete |
| `revold_pairs` | ppa | 717 passed candidates of the old REvolution runs, in 133 problems | none |
| `revold_failed` | synth | 600 failed candidates of the old REvolution runs (no Markdown files) | none |
| `revolution_spread_check` | ppa | 30: v0 and 9 variants each of controller, uart, tv80 | the frozen `revolution_pairs` plan |
| `revold_pairs_sample`, `revold_failed_sample` | ppa, synth | the samples of VERIFICATION.md, item 8 | none |

The frozen files of `synth_base`, `rtllm_llm`, `revolution_pairs`, and `area_power` exist already
(made on 2026-10-09 with no tool run).

## The commands

```bash
cd /users/micas/scuycken/workspace/JEV_RTL
python3.12 -m harness selftest                 # checks with no tool run
python3.12 -m harness plan area_power          # show a plan
python3.12 -m harness label ppa --plan area_power --limit 20    # run the next 20 designs
python3.12 -m harness status                   # records per job and status
python3.12 -m harness build all                # write data/questions/<test>.jsonl
python3.12 -m harness reclassify               # synth records again from their logs, no tool run
```

Options of `label`: `--limit N` (the next N designs with no record), `--only ID ...` (named designs),
`--dry-run` (make the run folders, start no tool), and `--shard I/N` (the plan positions p with
p % N == I, so N processes share one plan). The environment variable `JEV_TOOL_SLOTS=N` allows N
tools at the same time (default 1). `JEV_WORK_DIR` selects another work folder.

## The launch sequence for MV

Start with a pilot of each job. Then I check the pilot records before the full runs.

**Pilot** (about 1 hour with one license):

```bash
python3.12 -m harness label synth --plan synth_base --limit 20
python3.12 -m harness label ppa --plan revolution_pairs --limit 20
python3.12 -m harness label ppa --plan area_power --limit 20
python3.12 -m harness status
```

**Full runs** (in this order, because of the "Needs first" column):

| Step | Command | Designs | Tool time with one license (estimate) |
|---|---|---|---|
| 1 | `label synth --plan synth_base` | 531 | up to 10 h |
| 2 | `label synth --plan rtllm_llm` | 290 | up to 6 h |
| 3 | `label synth --plan synth_mutants` | up to 800 | 5 to 10 h |
| 4 | `label synth --plan synth_traps` | up to 120 | 2 h |
| 5 | `label ppa --plan revolution_pairs` | 526 | at least 12 h |
| 6 | `label ppa --plan area_power` | 914 | at least 20 h |
| 7 | `label period --plan timing` | 160 | about 30 h |
| 8 | `build all` | | seconds, no tool |

The estimates use the validation times: about 70 to 74 s for step 2 of a small design, 7 to 11 s for
step 4, and 4 s for a design that fails at `analyze`. Larger designs take longer, so the ppa and
period times are lower limits. With `JEV_TOOL_SLOTS=2` and two processes (`--shard 0/2` and
`--shard 1/2`), the time is about half, but the job then uses two DC licenses of the shared pool.

## After a run

- `python3.12 -m harness reclassify` classifies the synth records again from their logs. Run it
  after a change of the rules in `harness/synthcheck.py`. It refuses to run while a `harness label`
  process is active, because both write the same file.
- After the pilot of 2026-10-09, run `reclassify` once: 3 pilot records need the CMD-036 rule (see
  VERIFICATION.md, item 7).

## Dataset v1, the runner, and the scorer

- The job `design` (vlog, step 2, and step 4) and the plan `dataset_v1` make dataset v1
  (DATASET.md). `build dataset_v1` writes `data/questions/dataset_v1.jsonl`.
- `python3.12 -m harness.runner FILE --model jev|kev` sends each request (only the state and the
  questions) and writes `FILE.<model>.answers.jsonl`. It resumes a stopped run. Jev needs the
  environment variable `TYPESAFE_API_KEY`. Kev needs the Kev server on mercury.
- `python3.12 -m harness.score FILE --model jev|kev` prints the metrics per question key.
- `python3.12 -m harness.fewshot` writes `data/questions/dataset_v1_fewshot3.jsonl`: the 725 test
  questions of dataset v1, one question per request, each with three solved development examples of
  its own metric in the new state field `examples` (MV, 2026-10-16). A pair question gets the
  examples of its metric. The data card next to the file gives the examples. Commands for the Kev
  run: `condor/README.md`, section 9.
- `python3.12 -m harness.compare BASE_Q BASE_A NEW_Q NEW_A` compares two answer files on the same
  questions: accuracy, balanced accuracy, and the paired McNemar test per question key.

## The question files

`build` writes one file per test to `data/questions/`. One record is one request to the model:

- `state`: the named fields of the test (for example `rtl`, `top`, `flow`, `clock`, `tb_power`)
- `questions`: the typed questions in the format of the Jev API (`type`, `instructions`, `criteria`)
- `correct_answer`: the answer of each question
- `evidence`: the flow values (for example the area, the slack, the DC message IDs) and the run folder
- `split` (`dev` or `test`, 20% and 80%, by base design), `est_tokens`, and `over_token_limit`
  (above 8,000 tokens, the validated context of Kev-0.8B, 4B, and 9B)

A record above 30,000 tokens (estimate) is not written, because it does not fit in one Jev request.

## Not yet implemented

1. The Orchestrator pairs for `higher_fmax` and `less_energy` in pair_compare.
2. The control variants (R, M, U, O, P, and the test-specific controls) in the builders.
3. Three of the six trap kinds of synth_yesno (`while` loop, two clock edges, reset value).
4. The model runners (Jev API, Kev server, LLM baselines).
5. An exact token count. The harness estimates 2.68 characters per token (the MetRex median).
