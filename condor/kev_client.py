#!/usr/bin/env python3
"""Send JEV_RTL question records to a Kev server (or to the Jev API) and write the answers.

Usage:
    python3 kev_client.py --url http://127.0.0.1:8009 --model kev-4b@v1.0 \
        --out results/kev/pair_compare__kev-4b.jsonl data/questions/pair_compare.jsonl
    python3 kev_client.py --summary-only --out results/kev/pair_compare__kev-4b.jsonl

One question record is one request. The script appends one answer record per question record to
--out, and it skips the question records that already have an answer without an error. Thus a
stopped job continues where it stopped. If a question ID has more than one record in --out, the
last record is the valid one.

Each answer also includes the HTTP status and the full response in the format read by
`python3 -m harness.score QUESTIONS.jsonl --model kev --answers OUT.jsonl`.

The script uses only the Python standard library. It was tested with Python 3.6 and 3.12.
"""
import argparse
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict


def read_jsonl(path):
    """-> the records of a JSONL file. A line that a stopped job wrote only in part is skipped."""
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def last_per_question(path):
    """-> {question_id: the last answer record of that question} in an answer file."""
    last = {}
    if os.path.exists(path):
        for rec in read_jsonl(path):
            last[rec["question_id"]] = rec
    return last


def ask(url, payload, api_key, timeout):
    """-> (response body, wall time in ms). Raises urllib.error.HTTPError or URLError."""
    headers = {"content-type": "application/json"}
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url.rstrip("/") + "/v1/systemone", data=json.dumps(payload).encode(),
                                 headers=headers)
    start = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read())
    return body, (time.time() - start) * 1000


def predicted(answer, levels_from_one):
    """-> the predicted value of one API answer, in the form of the harness correct answers."""
    kind = answer.get("type")
    if kind == "choice":
        return answer["choice"]
    if kind == "noul":
        return answer["noul"] >= 0.5
    if kind == "score":
        # The API counts the score levels from 0 (the index in `criteria`). The harness levels
        # (area_level, power_level) count from 1.
        index = max(answer["probabilities"], key=lambda k: answer["probabilities"][k])
        return int(index) + (1 if levels_from_one else 0)
    return None


def summarize(out_path, levels_from_one=True):
    """Print the accuracy per test, question, and token group of an answer file."""
    last = last_per_question(out_path)
    errors = sum(1 for r in last.values() if r.get("error"))
    print(f"summary of {out_path}: {len(last)} question records, {errors} with an error")
    hits = defaultdict(Counter)
    for rec in last.values():
        if rec.get("error"):
            continue
        group = "over 8k tokens" if rec.get("over_token_limit") else "within 8k tokens"
        for name, correct in rec["correct_answer"].items():
            answer = rec["answers"].get(name)
            if answer is None:
                continue
            key = (rec["test"], name, group)
            hits[key]["n"] += 1
            hits[key]["correct"] += int(predicted(answer, levels_from_one) == correct)
    for (test, name, group), c in sorted(hits.items()):
        print(f"  {test:14s} {name:14s} {group:17s} {c['correct']:4d} of {c['n']:4d} correct "
              f"({100 * c['correct'] / c['n']:.1f}%)")
    latencies = sorted(r["latency_ms"] for r in last.values() if not r.get("error"))
    if latencies:
        print(f"  model time per request: median {latencies[len(latencies) // 2]:.0f} ms, "
              f"maximum {latencies[-1]:.0f} ms")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("questions", nargs="*", help="question files (JSONL) of the harness")
    ap.add_argument("--url", default="http://127.0.0.1:8009", help="the server (Kev) or https://api.typesafe.ai")
    ap.add_argument("--model", default="kev", help="the model name written into each answer record")
    ap.add_argument("--api-model", default="kev-latest", help="the `model` field of the request")
    ap.add_argument("--api-key-env", default="", help="the environment variable that holds an API key")
    ap.add_argument("--out", required=True, help="the answer file (JSONL); the script appends to it")
    ap.add_argument("--split", default="test", help="dev, test, or all")
    ap.add_argument("--max-est-tokens", type=int, default=0, help="skip records with more estimated tokens (0 = no limit)")
    ap.add_argument("--limit", type=int, default=0, help="answer at most this number of new records (0 = all)")
    ap.add_argument("--timeout", type=float, default=900, help="seconds for one request")
    ap.add_argument("--retries", type=int, default=3, help="attempts for a request that gets no response")
    ap.add_argument("--summary-only", action="store_true", help="only print the summary of --out")
    a = ap.parse_args()

    if a.summary_only:
        summarize(a.out)
        return 0

    api_key = os.environ.get(a.api_key_env, "") if a.api_key_env else ""
    done = {qid for qid, rec in last_per_question(a.out).items() if not rec.get("error")}
    todo = []
    for path in a.questions:
        for rec in read_jsonl(path):
            if a.split != "all" and rec.get("split") != a.split:
                continue
            if a.max_est_tokens and rec.get("est_tokens", 0) > a.max_est_tokens:
                continue
            if rec["question_id"] in done:
                continue
            todo.append(rec)
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(done)} records already answered, {len(todo)} to ask, model {a.model}, server {a.url}", flush=True)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    # A stopped job can leave a last line without its newline. Start the next record on a new line.
    if os.path.exists(a.out) and os.path.getsize(a.out) > 0:
        with open(a.out, "rb") as f:
            f.seek(-1, os.SEEK_END)
            needs_newline = f.read(1) != b"\n"
        if needs_newline:
            with open(a.out, "a") as f:
                f.write("\n")

    host = socket.gethostname()
    failures = 0
    with open(a.out, "a") as out:
        for i, rec in enumerate(todo, 1):
            payload = {"state": rec["state"], "model": a.api_model, "questions": rec["questions"]}
            answer = {"question_id": rec["question_id"], "test": rec.get("test"), "request": rec.get("request"),
                      "split": rec.get("split"), "model": a.model, "model_name": a.api_model,
                      "status": None, "response": None, "est_tokens": rec.get("est_tokens"),
                      "over_token_limit": rec.get("over_token_limit"), "correct_answer": rec.get("correct_answer"),
                      "host": host, "time": time.strftime("%Y-%m-%d %H:%M:%S")}
            for attempt in range(1, a.retries + 1):
                attempt_start = time.monotonic()
                try:
                    body, wall_ms = ask(a.url, payload, api_key, a.timeout)
                    answer.update(answers=body["answers"], input_tokens=body["usage"]["input_tokens"],
                                  latency_ms=body.get("latency_ms"), wall_ms=round(wall_ms, 1),
                                  status=200, response=body, seconds=round(wall_ms / 1000, 3), error=None)
                    break
                except urllib.error.HTTPError as e:
                    # The server refused this request (for example 422: the state is too long). Do not retry.
                    answer.update(status=e.code, seconds=round(time.monotonic() - attempt_start, 3),
                                  error=f"HTTP {e.code}: {e.read().decode(errors='replace')[:500]}")
                    break
                except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
                    answer.update(seconds=round(time.monotonic() - attempt_start, 3),
                                  error=f"no response (attempt {attempt}): {e}")
                    time.sleep(10 * attempt)
            out.write(json.dumps(answer) + "\n")
            out.flush()
            if answer["error"]:
                failures += 1
                print(f"[{i}/{len(todo)}] {rec['question_id']}: {answer['error'][:200]}", flush=True)
                if answer["error"].startswith("no response"):
                    print("the server does not respond; stop", flush=True)
                    break
            elif i == 1 or i % 25 == 0 or i == len(todo):
                print(f"[{i}/{len(todo)}] {rec['question_id']}: {answer['input_tokens']} tokens, "
                      f"{answer['latency_ms']} ms model time", flush=True)
    summarize(a.out)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
