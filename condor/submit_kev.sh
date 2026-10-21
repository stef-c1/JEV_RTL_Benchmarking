#!/usr/bin/env bash
# Submit one condor job that runs one Kev model on JEV_RTL question files.
#
# Usage: condor/submit_kev.sh [options] MODEL QUESTIONS.jsonl [QUESTIONS.jsonl ...]
#   MODEL  kev-0.8b, kev-4b, kev-9b, or kev-27b
#
# Options:
#   --dry               write and print the submit file, but do not submit it
#   --nice              submit as a nice user: lower priority, and other jobs can stop the job
#   --hours H           the maximum run time in hours
#   --gpu-gb G          the minimum GPU memory in GB
#   --disk-gb D         the scratch disk in GB
#   --client-args "A"   extra arguments for kev_client.py, for example "--limit 5"
#   --out DIR           the folder for the answer files (default: results/kev)
#
# The job, the question files, and the answer folder must be in the home folder, because all
# condor machines can read the home folder. /volume1 and /tmp are local disks of one machine.
set -euo pipefail

usage() { sed -n '2,17p' "$0"; exit 2; }
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT=$(dirname "$HERE")
DRY=0; NICE=0; HOURS=; GPU_GB=; DISK_GB=; CLIENT_ARGS=; OUT=$PROJECT/results/kev
while [ $# -gt 0 ]; do
    case "$1" in
        --dry) DRY=1; shift ;;
        --nice) NICE=1; shift ;;
        --hours) HOURS=$2; shift 2 ;;
        --gpu-gb) GPU_GB=$2; shift 2 ;;
        --disk-gb) DISK_GB=$2; shift 2 ;;
        --client-args) CLIENT_ARGS=$2; shift 2 ;;
        --out) OUT=$2; shift 2 ;;
        -h|--help) usage ;;
        -*) echo "unknown option: $1"; usage ;;
        *) break ;;
    esac
done
[ $# -ge 2 ] || usage
MODEL=$1; shift

# The resources of each model. GPU memory: the Kev README gives about 17 GB for Kev-9B and about
# 66 GB for Kev-27B (51 GB of weights plus the serving buffers). The host memory must hold the
# weights once, because Kev loads them in host memory first. The disk holds the Python
# environment (about 7.5 GB) and the weights. All GPUs need compute capability 8.0 or higher,
# because Kev serves in bf16.
#            GPU_GB  CPUS  MEM_GB  DISK_GB  HOURS
case "$MODEL" in
    kev-0.8b) set -- 8   2  12  15  4 "$@" ;;
    kev-4b)   set -- 20  2  24  25  4 "$@" ;;
    kev-9b)   set -- 30  2  40  40  6 "$@" ;;
    kev-27b)  set -- 75  4  80  75  8 "$@" ;;
    *) echo "unknown model: $MODEL"; usage ;;
esac
GPU_GB=${GPU_GB:-$1}; CPUS=$2; MEM_GB=$3; DISK_GB=${DISK_GB:-$4}; HOURS=${HOURS:-$5}
shift 5

QUESTIONS=()
for q in "$@"; do
    [ -f "$q" ] || { echo "no such question file: $q"; exit 2; }
    abs=$(cd "$(dirname "$q")" && pwd)/$(basename "$q")
    case "$abs" in
        /volume1/*|/tmp/*) echo "$abs is on a local disk; the condor machines cannot read it. Copy it into the home folder."; exit 2 ;;
    esac
    QUESTIONS+=("$abs")
done
mkdir -p "$OUT" "$HERE/logs" "$HERE/jobs"
OUT=$(cd "$OUT" && pwd)

STAMP=$(date +%Y%m%d_%H%M%S)
SUB=$HERE/jobs/${STAMP}_$MODEL.sub
{
    echo "# JEV_RTL: $MODEL on ${#QUESTIONS[@]} question file(s). Made by condor/submit_kev.sh on $(date '+%F %T')."
    echo "universe            = vanilla"
    echo "executable          = $HERE/kev_job.sh"
    echo "transfer_executable = false"
    echo "arguments           = \"$MODEL $OUT ${QUESTIONS[*]}\""
    echo "initialdir          = $PROJECT"
    echo "environment         = \"KEV_JOB_ID=\$(Cluster).\$(Process) KEV_CONDOR_DIR=$HERE KEV_CLIENT_ARGS='$CLIENT_ARGS'\""
    echo "request_cpus        = $CPUS"
    echo "request_memory      = ${MEM_GB}GB"
    echo "request_disk        = ${DISK_GB}GB"
    echo "request_gpus        = 1"
    # DriverVersion is advertised for CUDA GPUs; AMD advertises AmdDriverVersion instead.
    # Check each assigned device, rather than the machine's aggregate GPU properties.
    echo "require_gpus        = (DriverVersion =!= UNDEFINED) && (Capability >= 8.0) && (GlobalMemoryMb >= $(( GPU_GB * 1000 )))"
    echo "+RequestWalltime    = $(( HOURS * 3600 ))"
    echo "requirements        = (Arch == \"X86_64\") && Has_avx && (Machine != \"andromeda.esat.kuleuven.be\")"
    [ "$NICE" = 1 ] && echo "nice_user           = true"
    echo "output              = $HERE/logs/\$(Cluster).\$(Process).$MODEL.out"
    echo "error               = $HERE/logs/\$(Cluster).\$(Process).$MODEL.err"
    echo "log                 = $HERE/logs/\$(Cluster).\$(Process).$MODEL.log"
    echo "stream_output       = true"
    echo "stream_error        = true"
    echo "notification        = Error"
    echo "queue"
} > "$SUB"

cat "$SUB"
if [ "$DRY" = 1 ]; then
    echo "# --dry: the submit file is $SUB; it was not submitted."
    exit 0
fi
command -v condor_submit >/dev/null || { echo "condor_submit is not on this machine. Log in to a condor submit machine."; exit 1; }
condor_submit "$SUB"
cat <<EOF
Next steps:
  condor_q -nobatch                      # the state of your jobs
  condor_q -better-analyze <job ID>      # why a job does not start
  tail -f $HERE/logs/<job ID>.0.$MODEL.out
  condor_rm <job ID>                     # stop the job
Answers: $OUT/<question file>__$MODEL.jsonl
EOF
