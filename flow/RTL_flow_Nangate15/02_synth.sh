#!/usr/bin/bash
#
# Step 2 — synthesis with Synopsys Design Compiler.
#
# Maps the RTL onto the bundled NanGate 15nm library at the target
# frequency from config.sh, and writes the gate-level netlist that
# steps 3 and 4 use.
#
# Usage:  ./02_synth.sh
#         ./02_synth.sh --dry-run   write the script, do not run the tool
#
# Outputs (results/2_synth/):
#   <design>_mapped.v     gate-level netlist
#   <design>.sdc          the constraints Design Compiler used
#   area.rpt              area report
#   timing.rpt            timing report, the slack is in the first path
#   qor.rpt               summary of area, slack, and cell count
#   power_estimate.rpt    Design Compiler power estimate, no switching activity
#   violations.rpt        constraint violations
#   synth.tcl             the rendered script
#   synth.log             the full Design Compiler log
#

# shellcheck disable=SC1091
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

DRY_RUN=false
case "${1:-}" in
    --dry-run) DRY_RUN=true ;;
    "")        ;;
    *)         die "unknown option: $1. Use --dry-run." ;;
esac

[[ "$DRY_RUN" == true ]] || need_tool dc_shell "Design Compiler is not set up. $TOOL_HINT"

rm -rf "$SYNTH_DIR"
mkdir -p "$SYNTH_DIR"
synth_log="$SYNTH_DIR/synth.log"

banner "Step 2 — synthesis (Design Compiler, ${TECH_NAME})"
echo "  design : $DESIGN_NAME"
echo "  clock  : ${CLOCK_FREQ_MHZ} MHz (period ${CLK_PERIOD_NS} ns = ${CLK_PERIOD_LIB} ${TECH_TIME_UNIT_NAME})"

# ---- Read commands, one per RTL file ----
analyze_cmds=""
while read -r f; do
    analyze_cmds+="analyze -format sverilog [list {$f}]"$'\n'
done < <(rtl_abs_paths)

# ---- Clock constraint. A design without a clock port gets a virtual clock ----
if [[ -n "${CLOCK_PORT:-}" ]]; then
    clock_cmd="create_clock [get_ports ${CLOCK_PORT}] -name CORE_CLK -period ${CLK_PERIOD_LIB} -waveform [list 0 ${CLK_HALF_LIB}]"
else
    clock_cmd="create_clock -name CORE_CLK -period ${CLK_PERIOD_LIB}"
fi

# ---- The rest of the constraints ----
# config.sh states each time in nanoseconds, and the tool reads library
# time units, so every time value goes through to_lib_time first.
# MAX_FANOUT and IO_DELAY_FRACTION carry no unit, so they pass unchanged.
sdc=""
[[ -n "${MAX_TRANSITION:-}"        ]] && sdc+="set_max_transition $(to_lib_time "$MAX_TRANSITION") [current_design]"$'\n'
[[ -n "${MAX_FANOUT:-}"            ]] && sdc+="set_max_fanout ${MAX_FANOUT} [current_design]"$'\n'
[[ -n "${CLK_UNCERTAINTY_SETUP:-}" ]] && sdc+="set_clock_uncertainty $(to_lib_time "$CLK_UNCERTAINTY_SETUP") -setup [get_clocks CORE_CLK]"$'\n'
[[ -n "${CLK_UNCERTAINTY_HOLD:-}"  ]] && sdc+="set_clock_uncertainty $(to_lib_time "$CLK_UNCERTAINTY_HOLD") -hold [get_clocks CORE_CLK]"$'\n'
if [[ -n "${IO_DELAY_FRACTION:-}" ]]; then
    io_delay=$(awk -v p="$CLK_PERIOD_LIB" -v r="$IO_DELAY_FRACTION" 'BEGIN { printf "%.6g", p * r }')
    if [[ -n "${CLOCK_PORT:-}" ]]; then
        sdc+="set_input_delay -max ${io_delay} -clock CORE_CLK [remove_from_collection [all_inputs] [get_ports ${CLOCK_PORT}]]"$'\n'
    else
        sdc+="set_input_delay -max ${io_delay} -clock CORE_CLK [all_inputs]"$'\n'
    fi
    sdc+="set_output_delay -max ${io_delay} -clock CORE_CLK [all_outputs]"$'\n'
fi

# ---- The load the design drives, and the source that drives it ----
[[ -n "${OUTPUT_LOAD_FF:-}" ]] && sdc+="set_load ${OUTPUT_LOAD_FF} [all_outputs]"$'\n'
if [[ -n "${DRIVING_CELL:-}" ]]; then
    if [[ -n "${CLOCK_PORT:-}" ]]; then
        sdc+="set_driving_cell -lib_cell ${DRIVING_CELL} [remove_from_collection [all_inputs] [get_ports ${CLOCK_PORT}]]"$'\n'
    else
        sdc+="set_driving_cell -lib_cell ${DRIVING_CELL} [all_inputs]"$'\n'
    fi
fi

render "$PROJ_DIR/scripts/synth.tcl" "$SYNTH_DIR/synth.tcl" \
    "LIB_FILE=$TECH_DB" \
    "ANALYZE_CMDS=$analyze_cmds" \
    "DESIGN_NAME=$DESIGN_NAME" \
    "CLOCK_CMD=$clock_cmd" \
    "SDC_CONSTRAINTS=$sdc" \
    "COMPILE_FLAGS=${COMPILE_FLAGS:-}" \
    "SYNTH_DIR=$SYNTH_DIR"

if [[ "$DRY_RUN" == true ]]; then
    echo ""
    echo "Dry run. The script is $SYNTH_DIR/synth.tcl:"
    echo "----------------------------------------------------------------"
    cat "$SYNTH_DIR/synth.tcl"
    exit 0
fi

( cd "$SYNTH_DIR" && dc_shell -f "$SYNTH_DIR/synth.tcl" ) 2>&1 | tee "$synth_log"

[[ ${PIPESTATUS[0]} -eq 0 ]] || step_fail synth "dc_shell returned an error, see $synth_log"
grep -qi "^Error:" "$synth_log" && { grep -i "^Error:" "$synth_log" | head -10; step_fail synth "Design Compiler reported an error, see $synth_log"; }
[[ -f "$NETLIST" ]] || step_fail synth "no netlist was written: $NETLIST"

# ---- Report the two numbers that matter ----
area=$(awk '/^Total cell area:/ { print $4; exit }' "$SYNTH_DIR/area.rpt" 2>/dev/null)
slack=$(awk '/slack \(/ { print $NF; exit }' "$SYNTH_DIR/timing.rpt" 2>/dev/null)
echo ""
echo "  total cell area : ${area:-n/a} um2"
echo "  worst slack     : ${slack:-n/a} ${TECH_TIME_UNIT_NAME}"
step_ok synth "netlist: $NETLIST"
