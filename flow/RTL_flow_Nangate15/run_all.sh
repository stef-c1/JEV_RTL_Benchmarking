#!/usr/bin/bash
#
# Runs the setup check and the four steps in order, and stops at the first
# failure.
#
# Usage:  ./run_all.sh
#         ./run_all.sh --from 2      start at step 2
#         ./run_all.sh --no-check    skip the setup check
#
#

PROJ_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$PROJ_DIR"

FROM=1
CHECK=true
while [[ $# -gt 0 ]]; do
    case "$1" in
        --from)         FROM="$2"; shift 2 ;;
        --no-check)     CHECK=false; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

t0=$SECONDS

if [[ "$CHECK" == true ]]; then
    ./00_check.sh || {
        echo ""
        echo "The setup check failed, so no tool was started."
        exit 1
    }
fi

[[ $FROM -le 1 ]] && { ./01_verify.sh     || exit 1; }
[[ $FROM -le 2 ]] && { ./02_synth.sh      || exit 1; }
[[ $FROM -le 3 ]] && { ./03_verify_syn.sh || exit 1; }
[[ $FROM -le 4 ]] && { ./04_power.sh      || exit 1; }

./summary.sh
printf "\nAll steps passed in %dm%ds.\n" $(( (SECONDS-t0)/60 )) $(( (SECONDS-t0)%60 ))
