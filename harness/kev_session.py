"""Run a question file on Kev-4B on mercury: start the server, run the requests, stop the server.

    python3.12 -m harness.kev_session QUESTIONS.jsonl [--limit N]

The server always stops at the end, also after an error, because mercury is shared (memory note
kev-install-mercury: the server holds about 21 GB of RAM). The server log goes to
/volume1/users/scuycken/kev_serve_4b_<time>.log.
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request

from . import runner

KEV_DIR = "/volume1/users/scuycken/kev"
KEV_ENV = "/volume1/users/scuycken/kev_env.sh"
CMD = (f"source {KEV_ENV} && cd {KEV_DIR} && exec uv run --extra serve python -m kev.serve "
       "--run jaredpalmer/kev-4b@v1.0 --port 8009")


def ready(timeout=3):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8009/v1/models", timeout=timeout) as r:
            return r.status == 200
    except OSError:
        return False


def main(argv=None):
    p = argparse.ArgumentParser(prog="python3.12 -m harness.kev_session")
    p.add_argument("questions")
    p.add_argument("--limit", type=int)
    a = p.parse_args(argv)
    if ready():
        raise SystemExit("a server already answers on port 8009; stop it first")
    log_path = f"/volume1/users/scuycken/kev_serve_4b_{time.strftime('%Y%m%d_%H%M%S')}.log"
    with open(log_path, "w") as log:
        server = subprocess.Popen(["bash", "-c", CMD], stdout=log, stderr=subprocess.STDOUT,
                                  stdin=subprocess.DEVNULL, start_new_session=True)
    try:
        t0 = time.time()
        while not ready():
            if server.poll() is not None:
                raise SystemExit(f"the Kev server stopped during the start; see {log_path}")
            if time.time() - t0 > 900:
                raise SystemExit(f"the Kev server was not ready after 900 s; see {log_path}")
            time.sleep(5)
        print(f"Kev server ready after {time.time() - t0:.0f} s (log {log_path})", flush=True)
        runner.run(a.questions, "kev", limit=a.limit, workers=1, log=lambda *x: print(*x, flush=True))
    finally:
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(server.pid, sig)
                server.wait(timeout=30)
                break
            except (ProcessLookupError, subprocess.TimeoutExpired):
                continue
        print(f"Kev server stopped; port 8009 answers: {ready()}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
