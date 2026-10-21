#!/usr/bin/env bash
# Run one Kev model on JEV_RTL question files. The script runs on a condor node (see submit_kev.sh),
# or on any Linux machine for a test.
#
# Usage: kev_job.sh MODEL OUT_DIR QUESTIONS.jsonl [QUESTIONS.jsonl ...]
#   MODEL    kev-0.8b, kev-4b, kev-9b, or kev-27b. The job always loads the Hub tag v1.0.
#   OUT_DIR  the folder for the answer files: <question file name>__<MODEL>.jsonl
#
# Environment variables:
#   KEV_SCRATCH      the work folder for uv, Python, the environment, and the model weights. On condor,
#                    the default is the job scratch folder, which condor deletes after the job. Outside
#                    condor, you must set it (for example to a folder on /volume1). The folder is kept,
#                    so a second run uses the downloads again.
#   KEV_CLIENT_ARGS  extra arguments for kev_client.py, for example "--limit 5" or "--split all".
#   KEV_JOB_ID       a label for the log files (submit_kev.sh sets it to the condor job ID).
#   KEV_CONDOR_DIR   the folder of this script and kev_src. submit_kev.sh sets it, because condor can
#                    run the script from another folder.
#   Kev's own settings (KEV_DTYPE, KEV_PREFIX_CACHE, ...) go to the Kev server unchanged.
set -euo pipefail
export PATH=/usr/local/bin:/usr/bin:/bin${PATH:+:$PATH}

if [ $# -lt 3 ]; then
    sed -n '2,18p' "$0"
    exit 2
fi
MODEL=$1
OUT_DIR=$2
shift 2
case "$MODEL" in
    kev-0.8b|kev-4b|kev-9b|kev-27b) ;;
    *) echo "unknown model: $MODEL"; exit 2 ;;
esac

HERE=${KEV_CONDOR_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
UV_VERSION=0.12.24
RUN=jaredpalmer/$MODEL@v1.0
JOB_ID=${KEV_JOB_ID:-local_$$}

if [ -n "${_CONDOR_SCRATCH_DIR:-}" ]; then
    SCRATCH=${KEV_SCRATCH:-$_CONDOR_SCRATCH_DIR/kev}
elif [ -n "${KEV_SCRATCH:-}" ]; then
    SCRATCH=$KEV_SCRATCH
else
    echo "Set KEV_SCRATCH to a work folder with at least 20 GB free (not the home folder)."
    exit 2
fi
mkdir -p "$SCRATCH" "$OUT_DIR"
OUT_DIR=$(cd "$OUT_DIR" && pwd)
QUESTION_FILES=()
for q in "$@"; do QUESTION_FILES+=("$(cd "$(dirname "$q")" && pwd)/$(basename "$q")"); done

# Everything that the tools cache goes to the scratch folder (home quota).
export UV_CACHE_DIR=$SCRATCH/uv_cache
export UV_PYTHON_INSTALL_DIR=$SCRATCH/python
export UV_PROJECT_ENVIRONMENT=$SCRATCH/venv
export UV_PYTHON_PREFERENCE=only-managed
export HF_HOME=$SCRATCH/hf
export XDG_CACHE_HOME=$SCRATCH/cache
export TRITON_CACHE_DIR=$SCRATCH/cache/triton
export CUDA_CACHE_PATH=$SCRATCH/cache/nv
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX=$SCRATCH/cache/pycache
mkdir -p "$SCRATCH/bin"

echo "== job $JOB_ID: $MODEL on $(hostname) at $(date '+%F %T')"
echo "   scratch $SCRATCH ($(df -h --output=avail "$SCRATCH" | tail -1 | tr -d ' ') free)"
echo "   CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-unset}"
if command -v nvidia-smi >/dev/null; then
    nvidia-smi --query-gpu=index,name,memory.total,memory.used,driver_version --format=csv,noheader | sed 's/^/   GPU: /'
fi

# 1. uv, a fixed version.
UV=$SCRATCH/bin/uv
if [ ! -x "$UV" ] || [ "$("$UV" --version | cut -d' ' -f2)" != "$UV_VERSION" ]; then
    curl -sSfL "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-x86_64-unknown-linux-gnu.tar.gz" \
        | tar xz -C "$SCRATCH/bin" --strip-components=1
fi

# 2. The Python environment: the Kev copy in kev_src with the exact versions of its uv.lock.
#    The copy goes to the scratch folder, because the install writes build files next to the source.
SRC=$SCRATCH/kev_src
rm -rf "$SRC"
cp -r "$HERE/kev_src" "$SRC"
T0=$(date +%s)
(cd "$SRC" && "$UV" sync --frozen --no-dev --extra serve --python 3.12 --quiet)
PY=$UV_PROJECT_ENVIRONMENT/bin/python
echo "== environment ready in $(( $(date +%s) - T0 )) s: $("$PY" -c 'import torch; print("torch", torch.__version__, "cuda", torch.cuda.is_available())')"
if [ -n "${_CONDOR_SCRATCH_DIR:-}" ]; then
    "$PY" -c 'import torch; assert torch.cuda.is_available(), "Condor GPU job has no usable CUDA device"'
fi

# 3. The Kev server on a free port. The first start downloads the weights to HF_HOME.
PORT=$("$PY" -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')
SERVER_LOG=$SCRATCH/server_$JOB_ID.log
(cd "$SRC" && exec "$PY" -m kev.serve --run "$RUN" --port "$PORT") > "$SERVER_LOG" 2>&1 &
SERVER_PID=$!
SAMPLER_PID=
cleanup() {
    [ -n "$SAMPLER_PID" ] && kill "$SAMPLER_PID" 2>/dev/null || true
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
    mkdir -p "$OUT_DIR/logs"
    cp "$SERVER_LOG" "$OUT_DIR/logs/" 2>/dev/null || true
}
trap cleanup EXIT

# The GPU memory of the server process, every 5 s. The maximum shows the GPU memory that this
# model needs, so the next submit can request the right GPU size.
GPU_MEM_LOG=$SCRATCH/gpu_mem_$JOB_ID.txt
: > "$GPU_MEM_LOG"
if command -v nvidia-smi >/dev/null; then
    (while kill -0 "$SERVER_PID" 2>/dev/null; do
        nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits 2>/dev/null \
            | awk -F', *' -v p="$SERVER_PID" '$1 == p {print $2}' >> "$GPU_MEM_LOG"
        sleep 5
    done) &
    SAMPLER_PID=$!
fi

T0=$(date +%s)
until "$PY" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:$PORT/v1/models', timeout=5)" 2>/dev/null; do
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo "== the Kev server stopped; the end of its log:"
        tail -n 40 "$SERVER_LOG"
        exit 1
    fi
    if [ $(( $(date +%s) - T0 )) -gt 5400 ]; then
        echo "== the Kev server is not ready after 90 min; the end of its log:"
        tail -n 40 "$SERVER_LOG"
        exit 1
    fi
    sleep 5
done
echo "== server ready in $(( $(date +%s) - T0 )) s: $(grep -m1 '^serving' "$SERVER_LOG" || true)"

# 4. The questions, in order. Put a smoke file first: a failure stops the job before the full set.
# One answer file per question file. All successful answers remain available for a resumed job.
STATUS=0
for q in "${QUESTION_FILES[@]}"; do
    out=$OUT_DIR/$(basename "$q" .jsonl)__$MODEL.jsonl
    echo "== $q -> $out"
    # shellcheck disable=SC2086
    "$PY" "$HERE/kev_client.py" --url "http://127.0.0.1:$PORT" --model "$RUN" --out "$out" \
        ${KEV_CLIENT_ARGS:-} "$q" || { STATUS=1; break; }
    PYTHONPATH="$(dirname "$HERE")${PYTHONPATH:+:$PYTHONPATH}" "$PY" -m harness.score "$q" \
        --model kev --answers "$out" --split test || { STATUS=1; break; }
done

if [ -s "$GPU_MEM_LOG" ]; then
    echo "== maximum GPU memory of the Kev server: $(sort -n "$GPU_MEM_LOG" | tail -1) MiB"
fi
echo "== job $JOB_ID done at $(date '+%F %T'), status $STATUS"
exit $STATUS
