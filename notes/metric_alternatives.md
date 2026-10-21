# Alternatives to balanced accuracy for the yes/no questions (2026-10-19)

**Decision (MV, 2026-10-19):** the deck uses plain accuracy. Beside each bar, the deck gives the correct answers on the designs where the tool says "yes" and on those where it says "no" (for example "98 of 99 yes · 4 of 24 no"). Two dashed lines give the scores of always "no" and always "yes". MV rejected F1 after the explanation of how F1 works. The deck builder is `presentations/src/build_kev_findings.py` (functions `yes_no_panel` and `yes_no_counts`).

MV does not like the balanced accuracy of the deck, because a constant answer scores 50%.
This note lists the alternatives and computes each one on the test split of dataset v1.
The counts come from `presentations/data/verified_metrics_fewshot3.json` (section `compare`).
Experiment 1 is the run without examples. Experiment 2 is the run with three examples.

## The test set

| Question | yes designs | no designs | always "yes" scores |
|---|---|---|---|
| Does it compile? | 114 | 9 | 92.7% |
| Does it synthesize? | 99 | 24 | 80.5% |

The development split has 25 yes and 3 no designs for compile, and 19 yes and 9 no for synthesis.

## The candidates

Let TP = successes answered "yes", FN = successes answered "no", TN = failures answered "no", FP = failures answered "yes". Success recognition = TP / successes. Failure detection = TN / failures.

| Score | Formula | Constant answer | Perfect model |
|---|---|---|---|
| Plain accuracy | (TP + TN) / 123 | 92.7% or 7.3% (compile); 80.5% or 19.5% (synthesis) | 100% |
| Balanced accuracy (current) | (success recognition + failure detection) / 2 | 50% | 100% |
| Youden J (informedness) | success recognition + failure detection - 1 | 0% | 100% |
| Cohen's kappa | (accuracy - agreement expected from the answer mix) / (1 - that agreement) | 0 | 1 |
| Matthews correlation (MCC) | correlation between the answer and the truth | 0 | 1 |
| Worst-group rate | min(success recognition, failure detection) | 0% | 100% |
| Error reduction | 1 - (FN + FP) / errors of always "yes" | 0% (always "yes"), negative when worse | 100% |

## The values

Each cell gives experiment 1 / experiment 2. Percentages, except kappa and MCC.

### Does it compile?

| Model | answers yes/no | success recognition | failure detection | plain accuracy | balanced | Youden J | kappa | MCC | worst group | error reduction |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.8B | 4 yes / 119 no ; 1 yes / 122 no | 3.5% / 0.9% | 100.0% / 100.0% | 10.6% / 8.1% | 51.8% / 50.4% | 3.5% / 0.9% | 0.01 / 0.00 | 0.05 / 0.03 | 3.5% / 0.9% | -1122.2% / -1155.6% |
| 4B | 123 yes / 0 no ; 119 yes / 4 no | 100.0% / 99.1% | 0.0% / 33.3% | 92.7% / 94.3% | 50.0% / 66.2% | 0.0% / 32.5% | 0.00 / 0.44 | 0.00 / 0.48 | 0.0% / 33.3% | 0.0% / 22.2% |
| 9B | 121 yes / 2 no ; 117 yes / 6 no | 100.0% / 98.2% | 22.2% / 44.4% | 94.3% / 94.3% | 61.1% / 71.3% | 22.2% / 42.7% | 0.35 / 0.50 | 0.46 / 0.52 | 22.2% / 44.4% | 22.2% / 22.2% |
| 27B | 115 yes / 8 no ; 108 yes / 15 no | 100.0% / 94.7% | 88.9% / 100.0% | 99.2% / 95.1% | 94.4% / 97.4% | 88.9% / 94.7% | 0.94 / 0.72 | 0.94 / 0.75 | 88.9% / 94.7% | 88.9% / 33.3% |

### Does it synthesize?

| Model | answers yes/no | success recognition | failure detection | plain accuracy | balanced | Youden J | kappa | MCC | worst group | error reduction |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.8B | 123 yes / 0 no ; 0 yes / 123 no | 100.0% / 0.0% | 0.0% / 100.0% | 80.5% / 19.5% | 50.0% / 50.0% | 0.0% / 0.0% | 0.00 / 0.00 | 0.00 / 0.00 | 0.0% / 0.0% | 0.0% / -312.5% |
| 4B | 122 yes / 1 no ; 120 yes / 3 no | 99.0% / 99.0% | 0.0% / 8.3% | 79.7% / 81.3% | 49.5% / 53.7% | -1.0% / 7.3% | -0.02 / 0.11 | -0.04 / 0.19 | 0.0% / 8.3% | -4.2% / 4.2% |
| 9B | 119 yes / 4 no ; 118 yes / 5 no | 98.0% / 99.0% | 8.3% / 16.7% | 80.5% / 82.9% | 53.2% / 57.8% | 6.3% / 15.7% | 0.09 / 0.22 | 0.14 / 0.31 | 8.3% / 16.7% | 0.0% / 12.5% |
| 27B | 118 yes / 5 no ; 108 yes / 15 no | 99.0% / 97.0% | 16.7% / 50.0% | 82.9% / 87.8% | 57.8% / 73.5% | 15.7% / 47.0% | 0.22 / 0.55 | 0.31 / 0.57 | 16.7% / 50.0% | 12.5% / 37.5% |

## Notes on the trade-offs

- Plain accuracy is the only score with no formula. It needs the always "yes" line per question, because always "yes" scores 92.7% and 80.5%.
- With plain accuracy, the three examples lower the compile score of 27B from 99.2% to 95.1%: the model flags 6 good designs to catch the last failure. Balanced accuracy, Youden J, and the worst-group rate say that the examples help. Kappa, MCC, and error reduction say that they hurt.
- Youden J is balanced accuracy on another scale (J = 2 x balanced - 1). It changes the 50% of a constant answer into 0%.
- Kappa and MCC are the standard chance-corrected scores. Their values are close to each other. Both are harder to explain on a slide than a share of designs.
- The worst-group rate is plain to read: the model is right on at least X% of the designs in each group. It ignores how far the other group is above X%.
- A balanced test set removes the problem at the source: with equal yes and no counts, plain accuracy equals balanced accuracy, and always "yes" scores 50% without a formula. Dataset v1 cannot give this for compile (9 failures). Dataset v2 can add failing designs: a noncompile design costs one short flow run, and a synthesis mutant fails early in DC.


## F1 score (added 2026-10-19, MV asked)

F1 needs one positive class. The class of interest is the failure ("no"). Failure precision = failures answered "no" / all "no" answers. Failure recall = failures answered "no" / all failures (the failure detection above). F1 of "no" is the harmonic mean of the two. It does not count the successes answered "yes". F1 of "yes" is the same score with the success as the positive class. Macro F1 is the mean of the two.

### Does it compile?

| Model | answers yes/no | failure precision | failure recall | F1 of "no" | F1 of "yes" | macro F1 |
|---|---|---|---|---|---|---|
| 0.8B | 4 yes / 119 no ; 1 yes / 122 no | 7.6% / 7.4% | 100.0% / 100.0% | 14.1% / 13.7% | 6.8% / 1.7% | 10.4% / 7.7% |
| 4B | 123 yes / 0 no ; 119 yes / 4 no | 0.0% / 75.0% | 0.0% / 33.3% | 0.0% / 46.2% | 96.2% / 97.0% | 48.1% / 71.6% |
| 9B | 121 yes / 2 no ; 117 yes / 6 no | 100.0% / 66.7% | 22.2% / 44.4% | 36.4% / 53.3% | 97.0% / 97.0% | 66.7% / 75.2% |
| 27B | 115 yes / 8 no ; 108 yes / 15 no | 100.0% / 60.0% | 88.9% / 100.0% | 94.1% / 75.0% | 99.6% / 97.3% | 96.8% / 86.1% |

Constant answers: always "yes" gives F1 of "no" = 0%, F1 of "yes" = 96.2%, macro F1 = 48.1%. Always "no" gives F1 of "no" = 13.6%, F1 of "yes" = 0%, macro F1 = 6.8%.

### Does it synthesize?

| Model | answers yes/no | failure precision | failure recall | F1 of "no" | F1 of "yes" | macro F1 |
|---|---|---|---|---|---|---|
| 0.8B | 123 yes / 0 no ; 0 yes / 123 no | 0.0% / 19.5% | 0.0% / 100.0% | 0.0% / 32.7% | 89.2% / 0.0% | 44.6% / 16.3% |
| 4B | 122 yes / 1 no ; 120 yes / 3 no | 0.0% / 66.7% | 0.0% / 8.3% | 0.0% / 14.8% | 88.7% / 89.5% | 44.3% / 52.2% |
| 9B | 119 yes / 4 no ; 118 yes / 5 no | 50.0% / 80.0% | 8.3% / 16.7% | 14.3% / 27.6% | 89.0% / 90.3% | 51.6% / 59.0% |
| 27B | 118 yes / 5 no ; 108 yes / 15 no | 80.0% / 80.0% | 16.7% / 50.0% | 27.6% / 61.5% | 90.3% / 92.8% | 59.0% / 77.1% |

Constant answers: always "yes" gives F1 of "no" = 0%, F1 of "yes" = 89.2%, macro F1 = 44.6%. Always "no" gives F1 of "no" = 32.7%, F1 of "yes" = 0%, macro F1 = 16.3%.

Trade-offs:

- A constant answer has no fixed F1. Always "yes" scores 0%. Always "no" scores 13.6% (compile) and 32.7% (synthesis), because its recall is 100%.
- On synthesis with examples, 0.8B answers "no" to all 123 designs and gets F1 32.7%. That is above 9B (27.6%) and 4B (14.8%), which detect real failures with few false alarms.
- F1 depends on the class mix. With 9 compile failures, 6 false alarms cut the precision to 60%. The compile F1 and the synthesis F1 are not comparable.
- F1 of "yes" gives always "yes" 96.2% and 89.2%. It has the same problem as plain accuracy.
- Macro F1 gives always "yes" 48.1% and 44.6%, and always "no" 6.8% and 16.3%. It is a formula with a reference that moves.
