"""Send the requests of a question file to Jev or Kev, and store the answers.

    python3.12 -m harness.runner QUESTIONS.jsonl --model jev|kev [--limit N] [--workers N]

- jev: POST https://api.typesafe.ai/v1/systemone, model "jev-1.13.0", with the key in the
  environment variable TYPESAFE_API_KEY. jev-1.13.0 is the stable release (MV, 2026-10-16: only the
  stable release). The request names the version, not the alias jev-latest, because the alias
  moves to the next stable release.
- kev: POST http://127.0.0.1:8009/v1/systemone, model "kev-latest" (the Kev server on mercury,
  started as in the memory note kev-install-mercury). No key.

The answers go to <QUESTIONS>.<model>.answers.jsonl next to the question file, one line per request:
question_id, model, the HTTP status, the response body (answers, usage), the wall time, and an
error text if the request failed. A request that has an answer line with status 200 is skipped,
so a stopped run continues where it stopped. The model under test gets only the state and the
questions of the record: never the correct answer or the evidence.
"""
import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ENDPOINTS = {
    "jev": ("https://api.typesafe.ai/v1/systemone", "jev-1.13.0", "TYPESAFE_API_KEY"),
    "kev": ("http://127.0.0.1:8009/v1/systemone", "kev-latest", None),
}
RETRY_STATUS = {429, 500, 502, 503, 504, 529}


def answers_path(questions_file, model):
    return Path(f"{questions_file}.{model}.answers.jsonl")


def request_body(record, model_name):
    """The request: the state and the questions only."""
    return {"model": model_name, "state": record["state"], "questions": record["questions"]}


def post(url, body, key=None, timeout=1800, retries=6):
    """POST one request. Return (HTTP status, response body or error text, seconds)."""
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    delay = 2.0
    for attempt in range(retries):
        t0 = time.time()
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, json.loads(resp.read()), round(time.time() - t0, 2)
        except urllib.error.HTTPError as exc:
            text = exc.read().decode(errors="replace")[:2000]
            if exc.code in RETRY_STATUS and attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            return exc.code, text, round(time.time() - t0, 2)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            return None, f"{type(exc).__name__}: {exc}", round(time.time() - t0, 2)
    return None, "no attempt", 0.0


def done_ids(path):
    out = set()
    if path.exists():
        for line in open(path):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("status") == 200:
                out.add(r["question_id"])
    return out


def run(questions_file, model, limit=None, workers=None, log=print):
    url, model_name, key_var = ENDPOINTS[model]
    key = os.environ.get(key_var) if key_var else None
    if key_var and not key:
        raise SystemExit(f"set {key_var} first (the API key of TypeSafe)")
    records = [json.loads(l) for l in open(questions_file)]
    out_path = answers_path(questions_file, model)
    done = done_ids(out_path)
    todo = [r for r in records if r["question_id"] not in done]
    if limit is not None:
        todo = todo[:limit]
    workers = workers or (8 if model == "jev" else 1)
    log(f"{model}: {len(records)} requests in {questions_file}, {len(done)} answered, {len(todo)} to send "
        f"({workers} at a time) -> {out_path}")
    lock = threading.Lock()
    counter = {"n": 0, "errors": 0}

    def one(rec):
        status, body, seconds = post(url, request_body(rec, model_name), key)
        line = {"question_id": rec["question_id"], "model": model, "model_name": model_name, "status": status,
                "seconds": seconds, "response": body if status == 200 else None,
                "error": None if status == 200 else body}
        with lock:
            with open(out_path, "a") as f:
                f.write(json.dumps(line) + "\n")
            counter["n"] += 1
            counter["errors"] += status != 200
            log(f"[{counter['n']}/{len(todo)}] {rec['question_id'][:80]}: HTTP {status}, {seconds} s"
                + ("" if status == 200 else f", {str(body)[:160]}"))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(one, todo))
    log(f"{model}: {counter['n']} sent, {counter['errors']} errors")


def main(argv=None):
    p = argparse.ArgumentParser(prog="python3.12 -m harness.runner", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("questions")
    p.add_argument("--model", required=True, choices=sorted(ENDPOINTS))
    p.add_argument("--limit", type=int)
    p.add_argument("--workers", type=int)
    a = p.parse_args(argv)
    run(a.questions, a.model, a.limit, a.workers, log=lambda *x: print(*x, flush=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
