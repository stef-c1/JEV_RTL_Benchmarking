# Kev runs on condor

This folder runs the Kev models on the JEV_RTL question files with HTCondor ("condor"), the batch
system of ESAT. Mercury has the submit tools. Dataset v1 is built from all 159 completed design
runs: 151 retained designs, 348 requests, and 875 questions. Eight designs were excluded by the
dataset rules; some retained designs have no power measurement (see the data card).

## 1. Condor in short

- You describe a job in a submit file: the program, and the CPUs, memory, GPU, disk, and run time
  that it needs. Condor starts the job on a free machine that has these resources. The output of
  the job goes to log files.
- You submit a job from a submit machine with `condor_submit`. Centauri has no condor tools, so
  you cannot submit from centauri.
- On 2026-10-12 at 16:11, the pool had 161 machines: PSI 128, COSIC 25, MICAS 4, STADIUS 3, and
  SYSGRP 1. Source: <https://homes.esat.kuleuven.be/~deknuydt/condor_overview.shtml>.
- The GPUs of the machines with running jobs at that time are below. The page does not show the
  machines without jobs, and it does not show the compute capability of the GPUs.

| GPU memory per GPU | Machines (GPUs per machine) | Matches the GPU memory request of |
|---|---|---|
| about 95 GB | cauchy (2) | all Kev models |
| about 79 GB | aristoteles (8) | all Kev models |
| about 44 to 47 GB | pythagoras (8), euler (2) | Kev-0.8B, Kev-4B, Kev-9B |
| about 24 GB | hawberry, fig, grape, etrog (3); myoko, lausu, chokai, nasu, emerald (1) | Kev-0.8B, Kev-4B |
| 16 GB or less | 23 other machines | Kev-0.8B |

- The rules in `Condor_REPO/condor-control/README.md`: do not SSH to a condor machine to run long
  CUDA jobs, and be efficient: do not block resources.
- The account scuycken has condor history on the same page: 1,471 CPU hours as a nice user.

## 2. How the scripts use condor efficiently

1. One job per model. The job loads the model one time and answers all records of all question
   files that it gets. The setup (downloads and model load) is a fixed cost per job.
2. The job requests only what the model needs (table below). A small request matches more
   machines, so the job starts sooner.
3. The job installs uv, Python 3.12, the Kev environment (the exact versions of Kev's `uv.lock`),
   and the weights on the scratch disk of the condor machine. Condor deletes the scratch disk after
   the job. Only the answers and the logs go to the home folder (about 0.5 kB per record).
4. A stopped job continues where it stopped: the client skips the records that already have an
   answer.
5. Pass a small smoke file before the full dataset. The model loads once, answers the smoke file,
   then continues with the full dataset only if the client and scorer succeeded. The prepared
   smoke file covers basic, performance, reason, and one pair in both orders (5 requests).
6. Each successful file is scored on the test split automatically. The raw API responses are
   preserved, and interrupted jobs resume from their successful answers.

| Model | GPU memory | CPUs | Host memory | Scratch disk | Run time |
|---|---|---|---|---|---|
| kev-0.8b | 8 GB or more | 2 | 12 GB | 15 GB | 4 h |
| kev-4b | 20 GB or more | 2 | 24 GB | 25 GB | 4 h |
| kev-9b | 30 GB or more | 2 | 40 GB | 40 GB | 6 h |
| kev-27b | 75 GB or more | 4 | 80 GB | 75 GB | 8 h |

- All jobs require an NVIDIA CUDA GPU with compute capability 8.0 or higher, because the
  installed PyTorch build uses CUDA and Kev serves in bf16. `require_gpus` checks the CUDA
  `DriverVersion`, capability, and memory of each assigned GPU. Memory and capability alone also
  matched an AMD GPU in the first real submission; that job stopped before inference.
- The Kev README gives about 17 GB of GPU memory for Kev-9B and about 66 GB for Kev-27B. Kev loads
  the weights in host memory first, so the host memory must hold the weights one time.
- The options `--gpu-gb`, `--disk-gb`, and `--hours` change these values. At the end, each job log
  gives the maximum GPU memory of the Kev server. Use it to set `--gpu-gb` for the next job.

## 3. The commands

Run these commands on mercury:

```bash
cd /users/micas/scuycken/workspace/JEV_RTL

# 1. Smoke test, then the complete dataset, using Kev-0.8B v1.0
condor/submit_kev.sh --out results/kev/dataset_v1_kev-0.8b_20261014 \
    --client-args "--split all" kev-0.8b \
    data/pilot/dataset_v1_smoke.jsonl data/questions/dataset_v1.jsonl

# 2. Watch the job
condor_q -nobatch                          # the state of your jobs: I = idle, R = running, H = held
condor_q -better-analyze <job ID>          # why a job stays idle
tail -f condor/logs/<job ID>.0.kev-0.8b.out

# 3. Held-out test results: 281 requests containing 725 questions
python3.12 -m harness.score data/questions/dataset_v1.jsonl --model kev \
    --answers results/kev/dataset_v1_kev-0.8b_20261014/dataset_v1__kev-0.8b.jsonl \
    --split test

# Optional later runs: replace kev-0.8b with another model and choose its own output folder.

condor_rm <job ID>                         # stop a job
```

- `--dry` writes and shows the submit file, but does not submit it.
- `--nice` submits as a nice user. The job then has a lower priority, and other jobs can stop it.
  The job continues after a restart, so this is safe for long runs.
- The submit files go to `condor/jobs/`, the logs to `condor/logs/`, and the answers to
  `<output folder>/<question file>__<model>.jsonl`. The metrics go beside each answer file with
  `.score.json` appended. Scoring another split overwrites that metrics file; the answers remain.
- `--split all` answers development and test requests. Report the test metrics separately;
  development has 67 requests containing 150 questions. The scorer defaults to the test split.

## 4. The files

| File | What it does |
|---|---|
| `submit_kev.sh` | Writes the submit file for one model and submits it. |
| `kev_job.sh` | The job. It installs the environment on the scratch disk, starts the Kev server on a free port, runs the client, and stops the server. It also runs outside condor for a test (set `KEV_SCRATCH`). |
| `kev_client.py` | Sends each question record to the server and writes one answer record. Standard library only. `--summary-only` prints the accuracy of an answer file. |
| `kev_src/` | The Kev source of commit 5e42a7a (2026-10-05), with no changes: `kev/`, `pyproject.toml`, `uv.lock`, `README.md`, `LICENSE` (Apache-2.0). |

## 5. What still needs a real Condor job

1. **Submit machine checked on 2026-10-14:** mercury has `condor_submit` and `condor_q`.
2. **Dataset checked:** `data/questions/dataset_v1.jsonl` has 348 requests, with no estimated
   request above 8,000 tokens (maximum 7,966). These are estimates, not exact tokenizer counts.
   The run manifest records its SHA-256 fingerprint and the smoke request IDs.
3. **Only a Condor job can check these items.** The smoke phase checks all four:
   - The condor machines can read the home folder.
   - The condor machines can download from GitHub, PyPI, and Hugging Face.
   - The machines have the requested scratch disk.
   - The assigned GPU satisfies `require_gpus`, and the `+RequestWalltime` limit is supported.

## 6. The local test (2026-10-12, centauri, no condor)

- `kev_job.sh` ran on the CPU of centauri with Kev-0.8B and 3 pilot records.
- The first setup took 38 s for the environment (uv, Python 3.12, all packages) and 37 s to start
  the server (with the download of 1.8 GB of weights). The scratch folder then held 8.7 GB.
- The 3 records (9,016 to 9,211 tokens) took 20.6 to 21.9 s each on the CPU, with 0 errors.
- A second run skipped the 3 answered records and asked only the next record.
- Not tested: condor itself, a GPU, and the larger models.

## 7. Why the scripts do not use condor_send

`Condor_REPO/condor-control/condor_send` also writes submit files, but:

- Its `defaults.conf` holds the settings of its author: his conda path in `INITCOMMAND`.
- It limits each job to Fedora machines (`DISTRIBUTION = 'Fedora'`).
- It sends an e-mail for each job (`Notification = Always`).
- It needs the Python package `six`.

`submit_kev.sh` uses the same ESAT job attributes as `condor_send`.

## 8. Dataset v1 run completed on 2026-10-15

- Job `4.0` ran Kev-0.8B v1.0 on euler's NVIDIA GeForce RTX 3080 Ti, after job `3.0` stopped
  before inference on an incompatible AMD GPU. The GPU selection rule now requires CUDA.
- The 5-request smoke test succeeded, followed by all 348 dataset requests (875 questions), with
  zero HTTP errors. All 725 held-out test questions were scored, with no missing answers.
- The job took 125 seconds including setup. The full dataset requests took 52.0 seconds of wall
  time in total. Median model latency was 109 ms per request, and the maximum sampled GPU memory
  was 7,036 MiB. Actual input lengths were at most 7,706 tokens; no request exceeded 8,000.
- Results, test metrics, server logs, and the input fingerprint are in
  `results/kev/dataset_v1_kev-0.8b_20261014/`. The folder date is the preparation date.
- Execution succeeded, but model accuracy is weak: it predicted that every test design
  synthesizes, and gave the same area level and reachable-frequency level to every performance
  request in the test split. Read the per-question metrics before interpreting accuracy.

## 9. The few-shot run (prepared on 2026-10-16)

MV asked for a second Kev run with three solved examples in the context of each question: for
compilation 1 design that compiles and 2 that fail, with the labels; the same for synthesis. A power
question gets three designs with only their exact power results, and the same for area and frequency,
also for the pair questions. `python3.12 -m harness.fewshot` writes the question file from
`data/questions/dataset_v1.jsonl` (no tool run). The data card
`data/questions/dataset_v1_fewshot3.card.md` gives the three examples of each question, as the model
reads them.

- The file has the 725 test questions of the first run, in 725 requests: one question per request,
  because each question gets the examples of its own metric.
- Failed compile and synthesis examples also show the first vlog or DC error. The reason question gets
  three failed designs, each with its class and the first DC error.
- The level questions show the exact value and the level of each example. The pair questions use the
  examples of their metric (smaller_area: area, lower_power: power, higher_reach: frequency), with the
  exact values only.
- The examples are development designs, so the file has no development requests. No test design
  has the base design or the function (top module, or VerilogEval problem) of an example.
- Three requests have more than 8,192 tokens, all of the design `metrex_19218` (7,706 tokens in the
  first run): slack 8,607, power 8,534, and area 8,226 tokens. Kev-0.8B, 4B, and 9B are validated up
  to 8,192 tokens. The answer file marks these requests with `over_token_limit`.
- Kev-0.8B gets `--gpu-gb 12` (8 in the first run). Its first job used 7,036 MiB with requests of up
  to 7,706 tokens, and the longest request is now 8,607 tokens.

The commands, on mercury:

```bash
cd /users/micas/scuycken/workspace/JEV_RTL
condor/submit_kev.sh --gpu-gb 12 --out results/kev/dataset_v1_fewshot3_kev-0.8b_20261016 kev-0.8b \
    data/pilot/dataset_v1_fewshot3_smoke.jsonl data/questions/dataset_v1_fewshot3.jsonl
condor/submit_kev.sh --out results/kev/dataset_v1_fewshot3_kev-4b_20261016 kev-4b \
    data/pilot/dataset_v1_fewshot3_smoke.jsonl data/questions/dataset_v1_fewshot3.jsonl
condor/submit_kev.sh --out results/kev/dataset_v1_fewshot3_kev-9b_20261016 kev-9b \
    data/pilot/dataset_v1_fewshot3_smoke.jsonl data/questions/dataset_v1_fewshot3.jsonl
condor/submit_kev.sh --out results/kev/dataset_v1_fewshot3_kev-27b_20261016 kev-27b \
    data/pilot/dataset_v1_fewshot3_smoke.jsonl data/questions/dataset_v1_fewshot3.jsonl
```

After a job, compare the few-shot answers with the first run on the same 725 test questions
(accuracy, balanced accuracy, and the paired McNemar test per question key). For Kev-4B:

```bash
python3.12 -m harness.compare \
    data/questions/dataset_v1.jsonl results/kev/dataset_v1_kev-4b_20261015/dataset_v1__kev-4b.jsonl \
    data/questions/dataset_v1_fewshot3.jsonl \
    results/kev/dataset_v1_fewshot3_kev-4b_20261016/dataset_v1_fewshot3__kev-4b.jsonl
```

The first-run answers of Kev-0.8B are in `results/kev/dataset_v1_kev-0.8b_20261014/`.

The run of 2026-10-16: the four jobs were submitted at 15:39 (jobs 8.0 to 11.0). All four completed with
exit status 0, 725 of 725 answers, and 0 errors. The input tokens of each answer are equal to the
builder counts. Each results folder has a `manifest.json` and `compare_with_dataset_v1.json`. The
table of the four models: `results/kev/dataset_v1_fewshot3_summary.md`.

| Job | Model | Host and GPU | Wait in the queue | Run time | Maximum GPU memory |
|---|---|---|---|---|---|
| 8.0 | Kev-0.8B | goryu, RTX 5060 Ti 16 GB | 3 s | 4 min 37 s | 6,668 MiB |
| 9.0 | Kev-4B | hawberry, RTX 3090 24 GB | 2 s | 10 min 1 s | 21,736 MiB |
| 10.0 | Kev-9B | euler, RTX PRO 5000 Blackwell 48 GB | 10 min 22 s | 7 min 1 s | 28,458 MiB |
| 11.0 | Kev-27B | aristoteles, A100 80 GB | 4 h 17 min 48 s | 18 min 3 s | 74,418 MiB |

The maximum GPU memory of Kev-4B (21,736 MiB) is above its request of 20 GB, and that of Kev-27B
(74,418 MiB) is near its request of 75 GB. For a next run, request 24 GB for Kev-4B.
