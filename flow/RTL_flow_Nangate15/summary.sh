#!/usr/bin/bash
#
# Collects the results of the steps that ran into one table.
#
# Usage:  ./summary.sh
#
# Outputs:
#   results/summary.txt   the same table as a file
#   results/summary.csv   one row, for a spreadsheet
#

# shellcheck disable=SC1091
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

get_status () {
    local log="$1"
    [[ -f "$log" ]] || { echo "not run"; return; }
    grep -q "ALL TESTS PASSED" "$log" && echo "PASS" || echo "FAIL"
}

verify_status=$(get_status "$VERIFY_DIR/sim.log")
verify_syn_status=$(get_status "$VERIFY_SYN_DIR/sim.log")

area="n/a"; slack="n/a"; cells="n/a"
if [[ -f "$SYNTH_DIR/area.rpt" ]]; then
    area=$(awk '/^Total cell area:/ { print $4; exit }' "$SYNTH_DIR/area.rpt")
fi
if [[ -f "$SYNTH_DIR/qor.rpt" ]]; then
    slack=$(awk '/Critical Path Slack:/ { print $4; exit }' "$SYNTH_DIR/qor.rpt")
    cells=$(awk '/Leaf Cell Count:/ { print $4; exit }' "$SYNTH_DIR/qor.rpt")
fi
[[ -z "$slack" ]] && slack="n/a"

# The slack carries a minus sign when the design misses the clock, so the
# summary says which of the two it is, and at which frequency the critical
# path lands. That frequency is an estimate from this run, and synthesis at
# that frequency gives another netlist and another number.
slack_note=""
if [[ "$slack" =~ ^-?[0-9.]+$ ]]; then
    fmax=$(awk -v p="$CLK_PERIOD_NS" -v s="$slack" \
        'BEGIN { d = p - s; if (d > 0) printf "%.0f", 1000.0 / d }')
    if awk -v s="$slack" 'BEGIN { exit !(s >= 0) }'; then
        slack_note="MET, so the design runs at ${CLOCK_FREQ_MHZ} MHz"
        [[ -n "$fmax" ]] && slack_note+=", and up to about ${fmax} MHz"
    else
        slack_note="VIOLATED, so the design misses ${CLOCK_FREQ_MHZ} MHz"
        [[ -n "$fmax" ]] && slack_note+=", and reaches about ${fmax} MHz"
    fi
fi

power_total="n/a"; power_int="n/a"; power_sw="n/a"; power_leak="n/a"; power_total_w=""
if [[ -f "$POWER_DIR/power.rpt" ]]; then
    scale=$(pt_power_scale)
    w_int=$(pt_watts  "Cell Internal Power" "$POWER_DIR/power.rpt" "$scale")
    w_sw=$(pt_watts   "Net Switching Power" "$POWER_DIR/power.rpt" "$scale")
    w_leak=$(pt_watts "Cell Leakage Power"  "$POWER_DIR/power.rpt" "$scale")
    power_total_w=$(pt_watts "Total Power"  "$POWER_DIR/power.rpt" "$scale")
    [[ -n "$power_total_w" ]] || power_total_w=$(awk -v a="${w_int:-0}" -v b="${w_sw:-0}" -v c="${w_leak:-0}" 'BEGIN { printf "%.6g", a + b + c }')
    power_int=$(format_mw "$w_int")
    power_sw=$(format_mw "$w_sw")
    power_leak=$(format_mw "$w_leak")
    power_total=$(format_mw "$power_total_w")
fi

out="$RESULTS_DIR/summary.txt"
mkdir -p "$RESULTS_DIR"
{
    echo "================================================================"
    echo " ${DESIGN_NAME} — ${TECH_NAME} at ${CLOCK_FREQ_MHZ} MHz (${CLK_PERIOD_NS} ns)"
    echo "================================================================"
    printf " %-26s %s\n" "1. RTL verification"          "$verify_status"
    printf " %-26s %s\n" "2. synthesis, cell area"      "${area:-n/a} um2"
    printf " %-26s %s\n" "   worst slack"               "${slack} ${TECH_TIME_UNIT_NAME}${slack_note:+  ${slack_note}}"
    printf " %-26s %s\n" "   leaf cells"                "${cells:-n/a}"
    printf " %-26s %s\n" "3. gate-level verification"   "$verify_syn_status"
    printf " %-26s %s\n" "4. total power"               "${power_total}"
    printf " %-26s %s\n" "   cell internal"             "${power_int}"
    printf " %-26s %s\n" "   net switching"             "${power_sw}"
    printf " %-26s %s\n" "   cell leakage"              "${power_leak}"
    echo "================================================================"
} | tee "$out"

{
    echo "design,freq_mhz,period_ns,verify,area_um2,slack_${TECH_TIME_UNIT_NAME},leaf_cells,verify_syn,total_power_w"
    echo "${DESIGN_NAME},${CLOCK_FREQ_MHZ},${CLK_PERIOD_NS},${verify_status},${area},${slack},${cells},${verify_syn_status},${power_total_w}"
} > "$RESULTS_DIR/summary.csv"

echo ""
echo "Written to $out and $RESULTS_DIR/summary.csv"
