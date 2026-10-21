# Status and remaining work (2026-10-16, mercury)

## What exists now

| Item | State |
|---|---|
| Harness, test notes, flow, datasets | Ready. Self-test: 6 of 6 checks pass. |
| Dataset v1 design runs | All 159 planned designs have a label record. The builder retains 151 designs under the dataset rules. |
| Labels on mercury | synth: 20 records, all synthesize (after `reclassify` on 2026-10-13). ppa: 40 records, 39 usable (MV's pilot of 2026-10-09). |
| Labels on centauri | ppa: 30 records of `revolution_spread_check` (2026-10-10). Not yet on mercury. |
| Question files | `data/questions/dataset_v1.jsonl`: 348 requests, 875 questions. Test split: 281 requests, 725 questions; development: 67 requests, 150 questions. |
| TypeSafe API | Reachable from mercury: no key gives HTTP 403 "Must supply an API key!", a dummy key gives HTTP 401 (2026-10-13; again 403 with no key on 2026-10-16). Only the key is missing. |
| Jev runner | `harness.runner --model jev` sends `jev-1.13.0`, the stable release (MV, 2026-10-16: only the stable release, from mercury, not from Condor). Offline replay test passed on 2026-10-16 (VERIFICATION.md, item 13). |
| Kev-4B on mercury | Works with the question format of the harness. CPU only: measured 8.2 s (173 tokens), 32.5 s (1,203), 139.9 s (6,174), 231.9 s (9,861), that is about 4 s + 23 ms per input token. |
| Kev-0.8B on Condor | Job `4.0` completed on euler in 125 s, including setup and a smoke test. All 348 dataset requests answered without errors; all 725 test questions scored. Results: `results/kev/dataset_v1_kev-0.8b_20261014/`. Accuracy is weak; for example, every synthesis prediction is "yes" (see `condor/README.md`). |
| Kev-4B, 9B, 27B on Condor | Jobs `5.0`, `6.0`, `7.0` completed on 2026-10-15 (aristoteles, A100 80 GB). Results: `results/kev/dataset_v1_kev-<model>_20261015/`. |
| Few-shot Kev run | Completed on 2026-10-16 (jobs 8.0 to 11.0; all 725 answers of each model, 0 errors). Results: `results/kev/dataset_v1_fewshot3_kev-<model>_20261016/` and the four-model table `results/kev/dataset_v1_fewshot3_summary.md`. `data/questions/dataset_v1_fewshot3.jsonl`: the 725 test questions in 725 requests (one question each), each with three solved development examples of its own metric (`harness/fewshot.py`, data card next to the file). Commands: `condor/README.md`, section 9. Comparison with the first run: `python3.12 -m harness.compare`. |

## Found on 2026-10-13

1. `power_level` took all 20 router variants of the pilot, so near-identical designs filled level 3.
   Fixed: area_level and power_level use each base design once. The old REvolution candidates are
   only for pair_compare, and the `timing` plan excludes them.
2. The token estimate (2.68 characters per token) is 15% to 39% too high for the router records
   (Kev counted 6,174 and 9,861 tokens for estimates of 8,594 and 11,370).
3. Kev numbers the levels of a `score` answer from 0 (probability keys "0" to "4"). The correct
   answers of the harness number them from 1. The scorer must map the two.

## Dataset v1 plan (set on 2026-10-13; runs and Kev-0.8B evaluation now complete)

MV rejected the target of 500 questions per test. The dataset is now design-centric: 159 designs,
each with one flow run and a bundle of questions (DATASET.md). The validation run of 10 designs
passed (VERIFICATION.md, item 12).

| Step | Who | Size |
|---|---|---|
| `label design --plan dataset_v1` | MV starts it | 159 designs, about 3.5 to 5 h with one license |
| `build dataset_v1` | Claude | seconds, no tool |
| `harness.kev_session data/questions/dataset_v1.jsonl` | Claude or MV | about 4 h of CPU (estimate) |
| `harness.runner data/questions/dataset_v1.jsonl --model jev` | after the API key | minutes |
| `harness.score ... --model kev` and `--model jev` | Claude | seconds |

Commands for MV:

```bash
cd /users/micas/scuycken/workspace/JEV_RTL
python3.12 -m harness selftest
python3.12 -m harness label design --plan dataset_v1
python3.12 -m harness status design
```
