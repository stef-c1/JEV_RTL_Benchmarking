"""Offline test of `harness.runner --model jev` and `harness.score`: no TypeSafe key, no network, no cost.

    python3.12 probes/jev_runner_replay.py

A local server replays the stored Kev-27B responses of dataset_v1 in the Jev response format of the
TypeSafe docs: the top-level fields model, answers, and usage only (no latency_ms), with the model
"jev-1.13.0". The runner sends copies of the smoke file and of dataset_v1 to this server, then the
scorer scores the copy. The test passes if the server got only the state, the questions, and the
model, and if the test-split scores are identical to the stored Kev-27B scores. All copies and
answer files go to a temporary folder, which the script deletes at the end.
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import threading
from collections import Counter, defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness import runner, score  # noqa: E402

KEV_DIR = ROOT / "results/kev/dataset_v1_kev-27b_20261015"


def request_key(state, questions):
    return hashlib.sha256(json.dumps([state, questions], sort_keys=True).encode()).hexdigest()


def main():
    work = Path(tempfile.mkdtemp(prefix="jev_replay_"))
    try:
        full, smoke = work / "dataset_v1.jsonl", work / "dataset_v1_smoke.jsonl"
        shutil.copy(ROOT / "data/questions/dataset_v1.jsonl", full)
        shutil.copy(ROOT / "data/pilot/dataset_v1_smoke.jsonl", smoke)
        qids_by_key = defaultdict(set)
        for path in (full, smoke):
            for line in open(path):
                r = json.loads(line)
                qids_by_key[request_key(r["state"], r["questions"])].add(r["question_id"])
        kev = {}
        for line in open(KEV_DIR / "dataset_v1__kev-27b.jsonl"):
            a = json.loads(line)
            if a.get("status") == 200:
                kev[a["question_id"]] = a["response"]
        seen = Counter()
        lock = threading.Lock()

        class Replay(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                kev_resp = kev[sorted(qids_by_key[request_key(body["state"], body["questions"])])[0]]
                with lock:
                    seen[f"path {self.path}"] += 1
                    seen[f"auth {self.headers.get('Authorization')}"] += 1
                    seen[f"model {body['model']}"] += 1
                    seen[f"fields {','.join(sorted(body))}"] += 1
                data = json.dumps({"model": "jev-1.13.0", "answers": kev_resp["answers"],
                                   "usage": {"input_tokens": kev_resp["usage"]["input_tokens"],
                                             "output_tokens": kev_resp["usage"].get("output_tokens", 0)}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Replay)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url, model_name, key_var = runner.ENDPOINTS["jev"]
        print(f"runner settings for jev: {url}, model {model_name}, key variable {key_var}")
        runner.ENDPOINTS["jev"] = (f"http://127.0.0.1:{server.server_address[1]}/v1/systemone", model_name, key_var)
        os.environ[key_var] = "replay-test-key"
        log = []
        runner.run(str(smoke), "jev", log=log.append)
        runner.run(str(full), "jev", log=log.append)
        runner.run(str(full), "jev", log=log.append)  # a resumed run must send nothing
        server.shutdown()
        print("the server got:", dict(seen))
        print("the last runner line (the resumed run):", log[-1])

        n = sum(1 for path in (full, smoke) for _ in open(path))
        checks = {f"{n} requests, each with the model jev-1.13.0": seen["model jev-1.13.0"] == n,
                  "only model, questions, and state in each request": seen["fields model,questions,state"] == n,
                  "the Bearer key in each request": seen["auth Bearer replay-test-key"] == n,
                  "the resumed run sent nothing": log[-1].startswith("jev: 0 sent, 0 errors")}
        table, missing = score.score(str(full), "jev", "test")
        ref = json.load(open(KEV_DIR / "dataset_v1__kev-27b.jsonl.score.json"))
        checks["test-split scores identical to the stored Kev-27B scores"] = (
            ref["split"] == "test" and missing == ref["missing"] == 0 and json.loads(json.dumps(table)) == ref["table"])
        smoke_table, smoke_missing = score.score(str(smoke), "jev", "all")
        checks["smoke file: no missing and no unscored answer"] = (
            smoke_missing == 0 and sum(t["unscored"] for t in smoke_table) == 0)
        for name, ok in checks.items():
            print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        return 0 if all(checks.values()) else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
