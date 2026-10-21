#!/usr/bin/bash
#
# Step 4 — power analysis.
#
# Part A simulates the power testbench on the gate-level netlist and
# writes a VCD file. Part B annotates that switching activity onto the
# netlist in PrimeTime and reports the power.
#
# Usage:  ./04_power.sh            both parts
#         ./04_power.sh --sim-only only part A, the VCD
#         ./04_power.sh --pt-only  only part B, it reuses the VCD
#
# Outputs (results/4_power/):
#   <design>.vcd          switching activity
#   power.rpt             internal, switching, leakage, and total power
#   power_hierarchy.rpt   power per instance
#   power_by_cell.rpt     power per cell, largest first
#   activity_check.rpt    how much of the netlist the VCD annotates
#   power.tcl             the rendered script
#   sim.log, pt.log       tool logs
#

# shellcheck disable=SC1091
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

DO_SIM=true
DO_PT=true
DRY_RUN=false
case "${1:-}" in
    --sim-only) DO_PT=false ;;
    --pt-only)  DO_SIM=false ;;
    --dry-run)  DO_SIM=false; DRY_RUN=true ;;
    "")         ;;
    *)          die "unknown option: $1. Use --sim-only, --pt-only, or --dry-run." ;;
esac

[[ -f "$NETLIST" ]] || die "no netlist found. Run ./02_synth.sh first."

mkdir -p "$POWER_DIR"

# ================================================================
# Part A — gate-level simulation that writes the VCD
# ================================================================
if [[ "$DO_SIM" == true ]]; then
    need_tool vlog "QuestaSim is not set up. $TOOL_HINT"
    need_tool vsim "QuestaSim is not set up. $TOOL_HINT"

    tb_file=$(tb_path "$TB_POWER") || die "power testbench not found: tb/${TB_POWER}.sv"

    rm -f "$VCD_FILE"
    work_lib="$POWER_DIR/work"
    make_work_lib "$work_lib"
    compile_log="$POWER_DIR/compile.log"
    sim_log="$POWER_DIR/sim.log"

    banner "Step 4A — gate-level simulation for the VCD (QuestaSim)"
    echo "  netlist   : $NETLIST"
    echo "  testbench : $TB_POWER"

    mapfile -t defines < <(questa_defines)
    mapfile -t extra_args < <(tb_extra_abs_paths)

    vlog -sv -work "$work_lib" \
        "${defines[@]}" \
        +define+GATE_LEVEL_SIM \
        ${VLOG_EXTRA_ARGS[@]+"${VLOG_EXTRA_ARGS[@]}"} \
        ${extra_args[@]+"${extra_args[@]}"} \
        "$TECH_SIM_MODELS" \
        "$NETLIST" \
        "$tb_file" \
        2>&1 | tee "$compile_log"

    [[ ${PIPESTATUS[0]} -eq 0 ]] || step_fail power "compile error, see $compile_log"

    # The simulator runs inside the output folder, so a testbench that
    # dumps to a relative path still writes its VCD there.
    ( cd "$POWER_DIR" && vsim -c -voptargs=+acc -lib "$work_lib" "$TB_POWER" \
        ${VSIM_EXTRA_ARGS[@]+"${VSIM_EXTRA_ARGS[@]}"} \
        -do "run -all; quit -f" ) 2>&1 | tee "$sim_log"

    [[ ${PIPESTATUS[0]} -eq 0 ]] || step_fail power "simulation error, see $sim_log"

    # The testbench dumps into this folder. Take whatever VCD it wrote, and
    # use one name from here on.
    if [[ ! -f "$VCD_FILE" ]]; then
        found=$(find "$POWER_DIR" -maxdepth 1 -name '*.vcd' -newer "$compile_log" | head -1)
        [[ -n "$found" ]] || step_fail power "the testbench wrote no VCD file in $POWER_DIR"
        mv "$found" "$VCD_FILE"
    fi
    vcd_size=$(du -h "$VCD_FILE" | cut -f1)
    echo "  VCD: $VCD_FILE (${vcd_size})"
fi

# ================================================================
# Part B — PrimeTime power analysis
# ================================================================
if [[ "$DO_PT" == true ]]; then
    if [[ "$DRY_RUN" == false ]]; then
        need_tool pt_shell "PrimeTime is not set up. $TOOL_HINT"
        [[ -f "$VCD_FILE" ]] || die "no VCD found. Run ./04_power.sh --sim-only first."
    fi

    pt_log="$POWER_DIR/pt.log"

    banner "Step 4B — power analysis (PrimeTime, ${TECH_NAME})"
    echo "  netlist : $NETLIST"
    echo "  VCD     : $VCD_FILE"

    if [[ -n "${CLOCK_PORT:-}" ]]; then
        clock_cmd="create_clock [get_ports ${CLOCK_PORT}] -name CORE_CLK -period ${CLK_PERIOD_LIB} -waveform [list 0 ${CLK_HALF_LIB}]"
    else
        clock_cmd="create_clock -name CORE_CLK -period ${CLK_PERIOD_LIB}"
    fi

    # The times come from config.sh in nanoseconds, and PrimeTime reads
    # library time units, so to_lib_time converts each one.
    sdc=""
    [[ -n "${CLK_UNCERTAINTY_SETUP:-}" ]] && sdc+="set_clock_uncertainty $(to_lib_time "$CLK_UNCERTAINTY_SETUP") -setup [get_clocks CORE_CLK]"$'\n'
    [[ -n "${CLK_UNCERTAINTY_HOLD:-}"  ]] && sdc+="set_clock_uncertainty $(to_lib_time "$CLK_UNCERTAINTY_HOLD") -hold [get_clocks CORE_CLK]"$'\n'

    [[ -f "$TECH_DB" || "$DRY_RUN" == true ]] || die "the compiled library $TECH_DB is missing. Run ./02_synth.sh, it rebuilds the file."

    strip_path="${TB_POWER}/${DUT_INSTANCE}"

    render "$PROJ_DIR/scripts/power.tcl" "$POWER_DIR/power.tcl" \
        "LIB_FILE=$TECH_DB" \
        "NETLIST=$NETLIST" \
        "DESIGN_NAME=$DESIGN_NAME" \
        "CLOCK_CMD=$clock_cmd" \
        "SDC_CONSTRAINTS=$sdc" \
        "STRIP_PATH=${strip_path}" \
        "VCD_FILE=$VCD_FILE" \
        "POWER_DIR=$POWER_DIR"

    if [[ "$DRY_RUN" == true ]]; then
        echo ""
        echo "Dry run. The script is $POWER_DIR/power.tcl:"
        echo "----------------------------------------------------------------"
        cat "$POWER_DIR/power.tcl"
        exit 0
    fi

    ( cd "$POWER_DIR" && pt_shell -f "$POWER_DIR/power.tcl" ) 2>&1 | tee "$pt_log"

    [[ ${PIPESTATUS[0]} -eq 0 ]] || step_fail power "pt_shell returned an error, see $pt_log"
    grep -qi "^Error:" "$pt_log" && { grep -i "^Error:" "$pt_log" | head -10; step_fail power "PrimeTime reported an error, see $pt_log"; }
    [[ -f "$POWER_DIR/power.rpt" ]] || step_fail power "no power report was written"

    scale=$(pt_power_scale)
    p_int=$(pt_watts  "Cell Internal Power" "$POWER_DIR/power.rpt" "$scale")
    p_sw=$(pt_watts   "Net Switching Power" "$POWER_DIR/power.rpt" "$scale")
    p_leak=$(pt_watts "Cell Leakage Power"  "$POWER_DIR/power.rpt" "$scale")
    p_tot=$(pt_watts  "Total Power"         "$POWER_DIR/power.rpt" "$scale")
    [[ -n "$p_tot" ]] || p_tot=$(awk -v a="${p_int:-0}" -v b="${p_sw:-0}" -v c="${p_leak:-0}" 'BEGIN { printf "%.6g", a + b + c }')
    echo ""
    echo "  cell internal : $(format_mw "$p_int")"
    echo "  net switching : $(format_mw "$p_sw")"
    echo "  cell leakage  : $(format_mw "$p_leak")"
    echo "  total power   : $(format_mw "$p_tot")"

    # A total of zero means the VCD file annotated nothing. The usual cause
    # is a wrong instance name, because PrimeTime then strips a path that
    # does not exist and every net keeps its default activity.
    if [[ -z "$p_tot" ]] || (( $(awk -v v="${p_tot:-0}" 'BEGIN { print (v <= 0) }') )); then
        echo ""
        echo "  The power is zero, so the VCD file annotated nothing."
        echo "  PrimeTime stripped the path '${strip_path}', which is"
        echo "  TB_POWER/DUT_INSTANCE. Check that tb/${TB_POWER}.sv"
        echo "  instantiates ${DESIGN_NAME} with the instance name '${DUT_INSTANCE}',"
        echo "  and that the testbench dumps the design, not the ports alone."
        echo "  The annotation report is $POWER_DIR/activity_check.rpt"
        step_fail power "the power analysis produced no power"
    fi

    step_ok power "report: $POWER_DIR/power.rpt"
fi
