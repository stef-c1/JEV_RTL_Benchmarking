"""Compare two answer files of one model on the same questions (for example zero-shot and few-shot).

    python3.12 -m harness.compare BASE_QUESTIONS BASE_ANSWERS NEW_QUESTIONS NEW_ANSWERS [--split test] [--json FILE]

A question of the new file matches the base question with the same question key and with the base
question ID in its field `source_question_id` (harness/fewshot.py writes it), or with the same
question ID. For each question key the tool prints the number of matched questions, the accuracy
and the balanced accuracy in the two files, and the paired McNemar test: b = correct only in the
base file, c = correct only in the new file, and the exact two-sided p value of b against c. An
unanswered or unscored question counts as wrong in its file.
"""
import argparse
import json
import math
import sys
from collections import defaultdict

from .score import balanced, predicted_level


def answers_by_question(answers_file):
    """-> {question_id: response} of the latest complete record of each request (the rule of harness.score)."""
    latest = {}
    for line in open(answers_file):
        try:
            a = json.loads(line)
        except json.JSONDecodeError:
            continue
        latest[a["question_id"]] = a
    out = {}
    for qid, a in latest.items():
        if a.get("status") == 200 and not a.get("error"):
            out[qid] = a["response"]
        elif "status" not in a and not a.get("error") and isinstance(a.get("answers"), dict):
            out[qid] = {"answers": a["answers"]}
    return out


def correct(q, truth, ans):
    """True if the answer of one question equals the correct answer; None if there is no usable answer."""
    if not ans:
        return None
    if q["type"] == "noul":
        return None if ans.get("noul") is None else (ans["noul"] >= 0.5) == truth
    if q["type"] == "choice":
        return None if ans.get("choice") is None else ans["choice"] == truth
    best, _ = predicted_level(ans, q["criteria"])
    return None if best is None else best == truth


def results(questions_file, answers_file, split):
    """-> {(base question ID, key): (request, truth, correct or None)}."""
    answers = answers_by_question(answers_file)
    out = {}
    for line in open(questions_file):
        rec = json.loads(line)
        if split != "all" and rec.get("split") != split:
            continue
        resp = answers.get(rec["question_id"]) or {}
        base_id = rec.get("source_question_id", rec["question_id"])
        for key, q in rec["questions"].items():
            truth = rec["correct_answer"][key]
            out[(base_id, key)] = (rec["request"], truth, correct(q, truth, (resp.get("answers") or {}).get(key)))
    return out


def mcnemar_p(b, c):
    """The exact two-sided McNemar p value: a binomial test of b against b + c with p = 0.5."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def compare(base, new):
    rows = defaultdict(list)
    for qk in sorted(base.keys() & new.keys()):
        rows[qk[1]].append((base[qk][1], bool(base[qk][2]), bool(new[qk][2])))
    table = []
    for key, rs in sorted(rows.items()):
        b = sum(1 for _, x, y in rs if x and not y)
        c = sum(1 for _, x, y in rs if y and not x)
        by_class = {"base": defaultdict(list), "new": defaultdict(list)}
        for truth, x, y in rs:
            by_class["base"][str(truth)].append(x)
            by_class["new"][str(truth)].append(y)
        table.append({"key": key, "n": len(rs),
                      "accuracy_base": sum(x for _, x, _ in rs) / len(rs),
                      "accuracy_new": sum(y for _, _, y in rs) / len(rs),
                      "balanced_base": balanced(by_class["base"]), "balanced_new": balanced(by_class["new"]),
                      "only_base_correct": b, "only_new_correct": c, "mcnemar_p": mcnemar_p(b, c)})
    return table


def main(argv=None):
    p = argparse.ArgumentParser(prog="python3.12 -m harness.compare", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("base_questions")
    p.add_argument("base_answers")
    p.add_argument("new_questions")
    p.add_argument("new_answers")
    p.add_argument("--split", default="test", choices=["test", "dev", "all"])
    p.add_argument("--json", help="also write the table to this JSON file")
    a = p.parse_args(argv)
    base = results(a.base_questions, a.base_answers, a.split)
    new = results(a.new_questions, a.new_answers, a.split)
    matched = base.keys() & new.keys()
    print(f"matched questions: {len(matched)} (base {len(base)}, new {len(new)}); split {a.split}")
    print(f"  {'key':13s} {'n':>4s} {'acc base':>8s} {'acc new':>8s} {'bal base':>8s} {'bal new':>8s} "
          f"{'b':>4s} {'c':>4s} {'McNemar p':>9s}")
    table = compare(base, new)
    for t in table:
        print(f"  {t['key']:13s} {t['n']:4d} {t['accuracy_base']:8.3f} {t['accuracy_new']:8.3f} "
              f"{t['balanced_base']:8.3f} {t['balanced_new']:8.3f} {t['only_base_correct']:4d} "
              f"{t['only_new_correct']:4d} {t['mcnemar_p']:9.3g}")
    if a.json:
        with open(a.json, "w") as f:
            json.dump({"base": [a.base_questions, a.base_answers], "new": [a.new_questions, a.new_answers],
                       "split": a.split, "matched": len(matched), "table": table}, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
