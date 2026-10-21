#!/usr/bin/bash
#
# Step 1 — RTL verification.
#
# With VERIFY_MODE="sv" it compiles the RTL and the SystemVerilog
# testbench with QuestaSim, then simulates. The step passes when the
# testbench prints "ALL TESTS PASSED".
#
# With VERIFY_MODE="cocotb" it runs the cocotb tests on the RTL through
# QuestaSim. The step passes when every cocotb test passes.
#
# Usage:  ./01_verify.sh
#
# Outputs (results/1_verify/):
#   compile.log, sim.log        SystemVerilog mode
#   cocotb.log, results.xml     cocotb mode
#

# shellcheck disable=SC1091
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

need_tool vlog "QuestaSim is not set up. $TOOL_HINT"
need_tool vsim "QuestaSim is not set up. $TOOL_HINT"

rm -rf "$VERIFY_DIR"
mkdir -p "$VERIFY_DIR"

banner "Step 1 — RTL verification (QuestaSim, ${VERIFY_MODE})"
echo "  design    : $DESIGN_NAME"
echo "  clock     : ${CLOCK_FREQ_MHZ} MHz (period ${CLK_PERIOD_NS} ns)"

# ================================================================
# cocotb mode
# ================================================================
if [[ "$VERIFY_MODE" == "cocotb" ]]; then
    need_cocotb
    [[ -n "${COCOTB_TEST_MODULE:-}" ]] || die "COCOTB_TEST_MODULE is empty in $CONFIG_FILE"
    [[ -f "$PROJ_DIR/tb/${COCOTB_TEST_MODULE}.py" ]] || \
        die "cocotb test not found: tb/${COCOTB_TEST_MODULE}.py"

    if run_cocotb rtl "$VERIFY_DIR"; then
        step_ok verify "log: $VERIFY_DIR/cocotb.log"
    else
        step_fail verify "a cocotb test failed, see $VERIFY_DIR/cocotb.log"
    fi
    exit 0
fi

# ================================================================
# SystemVerilog mode
# ================================================================
tb_file=$(tb_path "$TB_VERIFY") || die "verification testbench not found: tb/${TB_VERIFY}.sv"
echo "  testbench : $TB_VERIFY"

work_lib="$VERIFY_DIR/work"
make_work_lib "$work_lib"
compile_log="$VERIFY_DIR/compile.log"
sim_log="$VERIFY_DIR/sim.log"

mapfile -t defines < <(questa_defines)
mapfile -t rtl_args < <(rtl_abs_paths)
mapfile -t extra_args < <(tb_extra_abs_paths)

vlog -sv -work "$work_lib" \
    "${defines[@]}" \
    ${VLOG_EXTRA_ARGS[@]+"${VLOG_EXTRA_ARGS[@]}"} \
    ${extra_args[@]+"${extra_args[@]}"} \
    "${rtl_args[@]}" \
    "$tb_file" \
    2>&1 | tee "$compile_log"

[[ ${PIPESTATUS[0]} -eq 0 ]] || step_fail verify "compile error, see $compile_log"

vsim -c -lib "$work_lib" "$TB_VERIFY" \
    ${VSIM_EXTRA_ARGS[@]+"${VSIM_EXTRA_ARGS[@]}"} \
    -do "run -all; quit -f" \
    2>&1 | tee "$sim_log"

[[ ${PIPESTATUS[0]} -eq 0 ]] || step_fail verify "simulation error, see $sim_log"

if grep -q "ALL TESTS PASSED" "$sim_log"; then
    step_ok verify "log: $sim_log"
else
    grep -E "^(FAIL|# \*\* (Error|Fatal))" "$sim_log" | head -20
    step_fail verify "the testbench did not print ALL TESTS PASSED, see $sim_log"
fi
