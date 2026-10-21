#!/usr/bin/bash
#
# Step 0 — checks the setup before any tool starts.
#
# It reads the configuration, the RTL, and the testbenches, and reports
# every mistake it can find. Run it after each change to config.sh. It
# starts no simulator and no synthesis tool, so it takes a second.
#
# Usage:  ./00_check.sh
#

# shellcheck disable=SC1091
. "$(dirname "${BASH_SOURCE[0]}")/common.sh"

errors=0
warnings=0

ok   () { printf "  \e[32mOK\e[0m     %s\n" "$1"; }
warn () { printf "  \e[33mWARN\e[0m   %s\n" "$1"; warnings=$((warnings + 1)); }
bad  () { printf "  \e[31mERROR\e[0m  %s\n" "$1"; errors=$((errors + 1)); }
hint () { printf "         %s\n" "$1"; }

banner "Step 0 — setup check"
echo "  configuration : $CONFIG_FILE"
echo "  design        : $DESIGN_NAME"
echo "  verify mode   : $VERIFY_MODE"

# ================================================================
# 0. The location of the project
#
# Design Compiler splits its library variables on every space, whatever
# the quoting, and it then stops with an internal error. QuestaSim has
# the same fault in vlog. Neither tool supports a space in a path.
# ================================================================
echo ""
echo "Project folder:"
if [[ "$PROJ_DIR" == *" "* ]]; then
    bad "the path of this folder holds a space: $PROJ_DIR"
    hint "Design Compiler and QuestaSim both fail on a path with a space."
    hint "Move the flow to a folder whose full path has no space, such as"
    hint "  /users/micas/scuycken/rtl_flow_freepdk15"
    hint "A symbolic link without a space also works, because the flow reads"
    hint "the path you start it from."
else
    ok "the path holds no space"
fi

# ================================================================
# 1. The tools
# ================================================================
echo ""
echo "Tool environment:"
if [[ -n "${TOOL_ENV_FILES_USED[*]:-}" ]]; then
    for entry in "${TOOL_ENV_FILES_USED[@]}"; do
        ok "sourced ${entry#$PROJ_DIR/}"
    done
else
    ok "TOOL_ENV_FILES is empty, so the tools come from the PATH of this shell"
fi

echo ""
echo "Tools:"
for tool in vlog vsim dc_shell pt_shell; do
    if path=$(command -v "$tool" 2>/dev/null); then
        ok "$tool  ->  $path"
    else
        bad "$tool is not on the PATH"
        hint "Correct the install folder in the setup file of that tool, in tools/."
        hint "Section 0 of config.sh names the file, and tools/README.md the lines."
    fi
done

if [[ -z "${MGLS_LICENSE_FILE:-}" ]]; then
    warn "MGLS_LICENSE_FILE is not set, so QuestaSim may find no license"
    hint "Set it in section 0 of config.sh when your shell does not set it."
else
    ok "QuestaSim license: $MGLS_LICENSE_FILE"
fi
if [[ -z "${SNPSLMD_LICENSE_FILE:-}" ]]; then
    warn "SNPSLMD_LICENSE_FILE is not set, so the Synopsys tools may find no license"
    hint "Set it in section 0 of config.sh when your shell does not set it."
else
    ok "Synopsys license: $SNPSLMD_LICENSE_FILE"
fi

# ================================================================
# 2. The technology files
# ================================================================
echo ""
echo "Technology (${TECH_NAME}):"
[[ -r "$TECH_DB" ]]         && ok "compiled library (.db)" || bad "the .db library is missing: $TECH_DB"
[[ -r "$TECH_SIM_MODELS" ]] && ok "cell models"            || bad "the cell models are missing: $TECH_SIM_MODELS"

# ================================================================
# 3. The design
# ================================================================
echo ""
echo "Design:"
if [[ "${CLOCK_FREQ_MHZ:-0}" =~ ^[0-9.]+$ ]] && (( $(awk -v f="${CLOCK_FREQ_MHZ:-0}" 'BEGIN { print (f > 0) }') )); then
    ok "clock: ${CLOCK_FREQ_MHZ} MHz, so the period is ${CLK_PERIOD_NS} ns"
else
    bad "CLOCK_FREQ_MHZ must be a number above zero, and it is '${CLOCK_FREQ_MHZ:-}'"
fi

for f in "${RTL_FILES[@]}"; do
    [[ -r "$PROJ_DIR/$f" ]] && ok "RTL file: $f" || bad "the RTL file is missing: $f"
done

# The top module must be declared in one of the RTL files.
top_file=""
for f in "${RTL_FILES[@]}"; do
    if grep -qE "^[[:space:]]*module[[:space:]]+${DESIGN_NAME}\b" "$PROJ_DIR/$f" 2>/dev/null; then
        top_file="$PROJ_DIR/$f"
        break
    fi
done
if [[ -n "$top_file" ]]; then
    ok "the top module '${DESIGN_NAME}' is in $(basename "$top_file")"
    if [[ "$top_file" != "$PROJ_DIR/${RTL_FILES[-1]}" ]]; then
        warn "the top module is not the last file in RTL_FILES"
        hint "List the files in dependency order, with the top module last."
    fi
else
    bad "no RTL file declares 'module ${DESIGN_NAME}'"
    hint "DESIGN_NAME must be the name of the top module, not the file name."
fi

# The clock port must exist in the top module.
if [[ -n "${CLOCK_PORT:-}" ]]; then
    if [[ -z "$top_file" ]]; then
        warn "the clock port cannot be checked, because the top module was not found"
    elif grep -qE "\b${CLOCK_PORT}\b" "$top_file"; then
        ok "the clock port '${CLOCK_PORT}' is in the top module"
    else
        bad "the clock port '${CLOCK_PORT}' is not in the top module"
        hint "Use the exact port name. For a design without a clock, set CLOCK_PORT=\"\"."
    fi
else
    warn "CLOCK_PORT is empty, so the design is treated as combinational"
fi

# ================================================================
# 4. The testbenches
# ================================================================
echo ""
echo "Verification:"

check_sv_tb () {
    local name="$1" kind="$2" file
    if ! file=$(tb_path "$name"); then
        bad "the $kind testbench is missing: tb/${name}.sv"
        return
    fi
    ok "$kind testbench: $(basename "$file")"

    if ! grep -qE "^[[:space:]]*module[[:space:]]+${name}\b" "$file"; then
        bad "tb/${name}.sv does not declare 'module ${name}'"
        hint "The file name and the module name must be the same."
    fi
    if ! grep -qE "\b${DESIGN_NAME}[[:space:]]+${DUT_INSTANCE}\b" "$file"; then
        bad "tb/${name}.sv does not instantiate ${DESIGN_NAME} as '${DUT_INSTANCE}'"
        hint "Either rename the instance, or change DUT_INSTANCE in the configuration."
        hint "A wrong instance name makes PrimeTime report a power of zero."
    fi
}

if [[ "$VERIFY_MODE" == "cocotb" ]]; then
    py="$PROJ_DIR/tb/${COCOTB_TEST_MODULE}.py"
    if [[ -r "$py" ]]; then
        ok "cocotb test: tb/${COCOTB_TEST_MODULE}.py"
        grep -q "@cocotb.test" "$py" && ok "the file holds cocotb tests" \
            || bad "tb/${COCOTB_TEST_MODULE}.py has no @cocotb.test function"
    else
        bad "the cocotb test is missing: tb/${COCOTB_TEST_MODULE}.py"
    fi

    if command -v "$PYTHON_BIN" >/dev/null 2>&1; then
        ok "Python: $(command -v "$PYTHON_BIN")"
        if ver=$("$PYTHON_BIN" -c "import cocotb; print(cocotb.__version__)" 2>/dev/null); then
            ok "cocotb ${ver}"
            cocotb_makefiles_dir >/dev/null 2>&1 && ok "cocotb makefiles" \
                || bad "the cocotb makefiles were not found"
        else
            bad "cocotb is not installed for $PYTHON_BIN"
            hint "Install it:  $PYTHON_BIN -m pip install --user cocotb"
        fi
    else
        bad "PYTHON_BIN '$PYTHON_BIN' is not on the PATH"
    fi
    command -v make >/dev/null 2>&1 && ok "make" || bad "make is not on the PATH, and cocotb needs it"
else
    check_sv_tb "$TB_VERIFY" "verification"
    tbv=$(tb_path "$TB_VERIFY" 2>/dev/null) || tbv=""
    if [[ -n "$tbv" ]]; then
        grep -q "ALL TESTS PASSED" "$tbv" && ok "the testbench can print ALL TESTS PASSED" \
            || bad "tb/${TB_VERIFY}.sv never prints \"ALL TESTS PASSED\", so the step always fails"
    fi
fi

echo ""
echo "Power:"
check_sv_tb "$TB_POWER" "power"
tbp=$(tb_path "$TB_POWER" 2>/dev/null) || tbp=""
if [[ -n "$tbp" ]]; then
    grep -q '\$dumpfile' "$tbp" && ok "the power testbench calls \$dumpfile" \
        || bad "tb/${TB_POWER}.sv never calls \$dumpfile, so no VCD file appears"
    grep -q '\$dumpvars' "$tbp" && ok "the power testbench calls \$dumpvars" \
        || bad "tb/${TB_POWER}.sv never calls \$dumpvars, so the VCD file stays empty"
fi

for f in "${TB_EXTRA_FILES[@]:-}"; do
    [[ -z "$f" ]] && continue
    [[ -r "$PROJ_DIR/$f" ]] && ok "extra file: $f" || bad "the extra file is missing: $f"
done

# ================================================================
# Result
# ================================================================
echo ""
echo "================================================================"
if [[ $errors -gt 0 ]]; then
    printf " \e[31m%d error(s)\e[0m and %d warning(s). Fix the errors first.\n" "$errors" "$warnings"
    echo "================================================================"
    exit 1
fi
if [[ $warnings -gt 0 ]]; then
    printf " No errors, and %d warning(s). You can run ./run_all.sh\n" "$warnings"
else
    printf " \e[32mEverything checks out.\e[0m Run ./run_all.sh\n"
fi
echo "================================================================"
