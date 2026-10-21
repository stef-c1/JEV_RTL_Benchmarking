# KEV findings deck

`KEV_RTL_findings_20261015.pptx` and `.pdf`: the results of the four KEV sizes on dataset v1, without
and with three solved examples. 29 slides: one slide per question, both experiments side by side.

## Rebuild

```bash
cd /users/micas/scuycken/workspace/JEV_RTL
PY=/users/micas/scuycken/no_backup/miniconda3/envs/mx_env/bin/python   # Python 3.9 with python-pptx 1.0.2
$PY presentations/src/build_kev_findings.py            # verifies every number from the saved answers, then builds
$PY presentations/src/build_kev_findings.py --cached   # reuses presentations/data/verified_metrics*.json
$PY presentations/src/render_qa.py                     # PDF, qa/slides/*.png, qa/contact_*.png
```

- `src/analyse_kev.py` recomputes and verifies the numbers; it writes `data/verified_metrics.json`,
  `data/verified_metrics_fewshot3.json`, and the CSV files.
- `src/build_kev_findings.py` asserts the claims of the titles, the tables, and the takeaways, and
  measures every title, subtitle, and bar label. If a text does not fit, the build stops and lists
  the texts.
- The build copies the previous PPTX to `backups/`. The old 57-slide deck of 19 October is
  `backups/KEV_RTL_findings_20261015_deck57_20261019.{pptx,pdf}`.
- `qa/final_review.json` records the review of each build. `qa/slide_manifest.json` lists the slides.
