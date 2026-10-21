#!/usr/bin/bash
#
# Step 3 — post-synthesis verification.
#
# Runs the same tests as step 1, but against the gate-level netlist from
# step 2 and the NanGate cell models. The cell models have no delays, so
# this step checks function, not timing. The timing report from step 2 is
# the timing result.
#
# The compile adds +define+GATE_LEVEL_SIM, and a cocotb test finds
# GATE_LEVEL_SIM=1 in its environment.
#
# Usage:  ./03_verify_syn.sh
#
# Outputs (results/3_verify_syn/):
#   compile.log, sim.log        SystemVerilog mode
#   cocotb.log, results.xml     cocotb mode
#

# shellcheck disable=SC1091
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

need_tool vlog "QuestaSim is not set up. $TOOL_HINT"
need_tool vsim "QuestaSim is not set up. $TOOL_HINT"

[[ -f "$NETLIST" ]] || die "no netlist found. Run ./02_synth.sh first."

rm -rf "$VERIFY_SYN_DIR"
mkdir -p "$VERIFY_SYN_DIR"

banner "Step 3 — post-synthesis verification (QuestaSim, gate level, ${VERIFY_MODE})"
echo "  netlist   : $NETLIST"

gate_hint () {
    echo ""
    echo "  A gate-level failure that the RTL run passes often comes from X values."
    echo "  Drive every input of the design before you release the reset."
}

# ================================================================
# cocotb mode
# ================================================================
if [[ "$VERIFY_MODE" == "cocotb" ]]; then
    need_cocotb
    [[ -f "$PROJ_DIR/tb/${COCOTB_TEST_MODULE}.py" ]] || \
        die "cocotb test not found: tb/${COCOTB_TEST_MODULE}.py"

    if run_cocotb gate "$VERIFY_SYN_DIR"; then
        step_ok verify_syn "log: $VERIFY_SYN_DIR/cocotb.log"
    else
        gate_hint
        step_fail verify_syn "a cocotb test failed, see $VERIFY_SYN_DIR/cocotb.log"
    fi
    exit 0
fi

# ================================================================
# SystemVerilog mode
# ================================================================
tb_file=$(tb_path "$TB_VERIFY") || die "verification testbench not found: tb/${TB_VERIFY}.sv"
echo "  testbench : $TB_VERIFY"

work_lib="$VERIFY_SYN_DIR/work"
make_work_lib "$work_lib"
compile_log="$VERIFY_SYN_DIR/compile.log"
sim_log="$VERIFY_SYN_DIR/sim.log"

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

[[ ${PIPESTATUS[0]} -eq 0 ]] || step_fail verify_syn "compile error, see $compile_log"

vsim -c -lib "$work_lib" "$TB_VERIFY" \
    ${VSIM_EXTRA_ARGS[@]+"${VSIM_EXTRA_ARGS[@]}"} \
    -do "run -all; quit -f" \
    2>&1 | tee "$sim_log"

[[ ${PIPESTATUS[0]} -eq 0 ]] || step_fail verify_syn "simulation error, see $sim_log"

if grep -q "ALL TESTS PASSED" "$sim_log"; then
    step_ok verify_syn "log: $sim_log"
else
    grep -E "^(FAIL|# \*\* (Error|Fatal))" "$sim_log" | head -20
    gate_hint
    step_fail verify_syn "the testbench did not print ALL TESTS PASSED, see $sim_log"
fi
