"""Score the answers of one model on a question file.

    python3.12 -m harness.score QUESTIONS.jsonl --model jev|kev [--split test|dev|all] [--answers FILE]

It reads QUESTIONS.jsonl and QUESTIONS.<model>.answers.jsonl (or --answers FILE), and prints one line per question key
(compiles, synthesizes, reason, slack, reach, area, power, and the pair keys):
  noul    accuracy at 0.5, balanced accuracy, Brier score, AUROC
  choice  accuracy, balanced accuracy (over the correct classes)
  score   exact-level accuracy, accuracy within one level, mean absolute error in levels
  pairs   also the position bias: the fraction of pairs with the same letter in both orders
It also writes the table as JSON next to the answers file.
The latest complete record for each request is used; a failed request counts as missing. Partial
JSON lines left by an interrupted writer are ignored. Legacy Condor answer files are also accepted.

The level of a score answer: Kev keys its probabilities "0" to "4" (0-based). The scorer maps a
digit key k to the level k + 1. A key that is the text of a criterion maps to the position of that
criterion. Another format counts as "unscored", so a new answer format never gives a false score.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from . import runner


def _level_from_key(key, criteria):
    if isinstance(key, str) and key.isdigit():
        return int(key) + 1
    if key in criteria:
        return criteria.index(key) + 1
    return None


def predicted_level(answer, criteria):
    probs = answer.get("probabilities") or {}
    if not probs:
        return None, None
    levels = {_level_from_key(k, criteria): v for k, v in probs.items()}
    if None in levels:
        return None, None
    best = max(levels, key=levels.get)
    expected = sum(level * p for level, p in levels.items()) / max(1e-12, sum(levels.values()))
    return best, expected


def auroc(pos, neg):
    """The probability that a random positive gets a higher yes probability than a random negative."""
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def balanced(correct_by_class):
    rates = [sum(v) / len(v) for v in correct_by_class.values() if v]
    return sum(rates) / len(rates) if rates else None


def score(questions_file, model, split="test", answers_file=None):
    records = {json.loads(l)["question_id"]: json.loads(l) for l in open(questions_file)}
    latest = {}
    with open(answers_file if answers_file is not None else runner.answers_path(questions_file, model)) as f:
        for line in f:
            try:
                a = json.loads(line)
            except json.JSONDecodeError:
                # A stopped writer can leave a partial record, also before a resumed run's records.
                continue
            latest[a["question_id"]] = a
    answers = {}
    for qid, a in latest.items():
        if a.get("status") == 200 and not a.get("error"):
            answers[qid] = a["response"]
        elif "status" not in a and not a.get("error") and isinstance(a.get("answers"), dict):
            # Condor clients before the status/response fields stored the API answers directly.
            answers[qid] = {"answers": a["answers"]}
    rows = defaultdict(list)          # (request, key) -> per-question results
    same_letter = defaultdict(dict)   # key -> pair id -> {order: letter}
    missing = 0
    for qid, rec in records.items():
        if split != "all" and rec.get("split") != split:
            continue
        resp = answers.get(qid)
        if resp is None:
            missing += 1
            continue
        for key, q in rec["questions"].items():
            truth = rec["correct_answer"][key]
            ans = (resp.get("answers") or {}).get(key) or {}
            row = {"truth": truth}
            if q["type"] == "noul":
                p = ans.get("noul")
                row.update(p=p, pred=(p >= 0.5) if p is not None else None)
            elif q["type"] == "choice":
                row.update(pred=ans.get("choice"), conf=ans.get("confidence"))
                if rec.get("request") == "pair":
                    pair_id, order = qid.rsplit(":", 1)
                    same_letter[key].setdefault(pair_id, {})[order] = ans.get("choice")
            else:
                best, expected = predicted_level(ans, q["criteria"])
                row.update(pred=best, expected=expected)
            row["type"] = q["type"]
            rows[(rec.get("request"), key)].append(row)
    table = []
    for (request, key), rs in sorted(rows.items(), key=lambda x: (str(x[0][0]), x[0][1])):
        kind = rs[0]["type"]
        scored = [r for r in rs if r["pred"] is not None]
        line = {"request": request, "key": key, "type": kind, "n": len(rs), "unscored": len(rs) - len(scored)}
        if scored:
            line["accuracy"] = sum(r["pred"] == r["truth"] for r in scored) / len(scored)
            by_class = defaultdict(list)
            for r in scored:
                by_class[r["truth"]].append(r["pred"] == r["truth"])
            line["balanced_accuracy"] = balanced(by_class)
            line["truth_counts"] = dict(Counter(str(r["truth"]) for r in scored))
            line["pred_counts"] = dict(Counter(str(r["pred"]) for r in scored))
        if kind == "noul" and scored:
            line["brier"] = sum((r["p"] - float(r["truth"])) ** 2 for r in scored) / len(scored)
            line["auroc"] = auroc([r["p"] for r in scored if r["truth"]], [r["p"] for r in scored if not r["truth"]])
        if kind == "score" and scored:
            line["within_one"] = sum(abs(r["pred"] - r["truth"]) <= 1 for r in scored) / len(scored)
            line["mae_levels"] = sum(abs(r["expected"] - r["truth"]) for r in scored) / len(scored)
        if request == "pair" and same_letter.get(key):
            both = [v for v in same_letter[key].values() if len(v) == 2]
            if both:
                line["same_letter_both_orders"] = sum(v["AB"] == v["BA"] for v in both) / len(both)
        table.append(line)
    return table, missing


def main(argv=None):
    p = argparse.ArgumentParser(prog="python3.12 -m harness.score", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("questions")
    p.add_argument("--model", required=True)
    p.add_argument("--split", default="test", choices=["test", "dev", "all"])
    p.add_argument("--answers", type=Path, help="answer JSONL file (default: QUESTIONS.<model>.answers.jsonl)")
    a = p.parse_args(argv)
    table, missing = score(a.questions, a.model, a.split, answers_file=a.answers)
    print(f"{a.model} on {a.questions} (split {a.split}); requests with no answer: {missing}")
    for t in table:
        extra = " ".join(f"{k}={t[k]:.3f}" for k in ("accuracy", "balanced_accuracy", "brier", "auroc",
                                                         "within_one", "mae_levels", "same_letter_both_orders")
                         if t.get(k) is not None)
        print(f"  {str(t['request']):12s} {t['key']:13s} {t['type']:6s} n={t['n']:4d} unscored={t['unscored']:3d} {extra}")
    out = Path(f"{a.answers if a.answers is not None else runner.answers_path(a.questions, a.model)}.score.json")
    out.write_text(json.dumps({"split": a.split, "missing": missing, "table": table}, indent=1))
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
