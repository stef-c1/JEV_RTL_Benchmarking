# Few-shot Kev run (2026-10-16) compared with the first run (2026-10-15)

The same 725 test questions. Each cell: the first run -> the run with three examples per question.
Source: compare_with_dataset_v1.json in each results folder (harness/compare.py).

## Balanced accuracy in %

A fixed answer to every question gives 50 on a yes/no question, and 1 / (number of true levels) on a
level question: 25 for slack, frequency, and power, 20 for area.

| Question (test questions) | Kev-0.8B | Kev-4B | Kev-9B | Kev-27B |
|---|---|---|---|---|
| Does it compile? (114 yes, 9 no) | 52 -> 50 | 50 -> 66 | 61 -> 71 | 94 -> 97 |
| Does it synthesize? (99 yes, 24 no) | 50 -> 50 | 49 -> 54 | 53 -> 58 | 58 -> 73 |
| Reason, 10 classes (16) | 18 -> 4 | 38 -> 44 | 50 -> 50 | 88 -> 75 |
| Slack level (92) | 20 -> 25 | 12 -> 20 | 1 -> 30 | 13 -> 29 |
| Frequency level (92) | 25 -> 24 | 21 -> 34 | 25 -> 24 | 25 -> 37 |
| Area level (92) | 20 -> 20 | 20 -> 49 | 47 -> 51 | 48 -> 42 |
| Power level (85) | 25 -> 0 | 27 -> 42 | 37 -> 32 | 23 -> 39 |
| Smaller area, pair (46) | 48 -> 50 | 76 -> 67 | 87 -> 76 | 78 -> 89 |
| Lower power, pair (44) | 64 -> 55 | 57 -> 64 | 66 -> 70 | 70 -> 80 |
| Higher frequency, pair (12) | 67 -> 50 | 83 -> 50 | 75 -> 75 | 83 -> 92 |

## Accuracy in %, with the paired McNemar test

Bold: p < 0.05 for the change of the correct answers (b = correct only in the first run, c = correct only
with examples).

| Question (test questions) | Kev-0.8B | Kev-4B | Kev-9B | Kev-27B |
|---|---|---|---|---|
| Does it compile? (114 yes, 9 no) | 11 -> 8 (p=0.38) | 93 -> 94 (p=0.62) | 94 -> 94 (p=1) | 99 -> 95 (p=0.12) |
| Does it synthesize? (99 yes, 24 no) | **80 -> 20** (p=5.2e-12) | 80 -> 81 (p=0.5) | 80 -> 83 (p=0.25) | 83 -> 88 (p=0.11) |
| Reason, 10 classes (16) | 31 -> 6 (p=0.22) | 56 -> 62 (p=1) | 69 -> 69 (p=1) | 94 -> 88 (p=1) |
| Slack level (92) | **9 -> 68** (p=1.5e-12) | 4 -> 11 (p=0.11) | **3 -> 16** (p=0.0042) | **33 -> 65** (p=1.5e-08) |
| Frequency level (92) | 14 -> 24 (p=0.11) | 12 -> 23 (p=0.064) | 14 -> 16 (p=0.85) | **14 -> 39** (p=1.5e-05) |
| Area level (92) | **36 -> 2** (p=3.7e-08) | 36 -> 50 (p=0.098) | 58 -> 54 (p=0.76) | **66 -> 52** (p=0.029) |
| Power level (85) | **27 -> 0** (p=2.4e-07) | 46 -> 40 (p=0.38) | 40 -> 28 (p=0.12) | **11 -> 42** (p=4.6e-07) |
| Smaller area, pair (46) | 48 -> 50 (p=1) | 76 -> 67 (p=0.39) | 87 -> 76 (p=0.27) | 78 -> 89 (p=0.062) |
| Lower power, pair (44) | 64 -> 55 (p=0.29) | 57 -> 64 (p=0.45) | 66 -> 70 (p=0.82) | 70 -> 80 (p=0.12) |
| Higher frequency, pair (12) | 67 -> 50 (p=0.62) | 83 -> 50 (p=0.12) | 75 -> 75 (p=1) | 83 -> 92 (p=1) |
