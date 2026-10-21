#!/usr/bin/bash
#
# common.sh — shared setup for all steps. Every step script sources it.
#
# It loads config.sh, computes the derived values, checks the inputs,
# and gives the steps their helper functions. Do not run it directly.
#

set -u
set -o pipefail

PROJ_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export PROJ_DIR
cd "$PROJ_DIR"

# ---- Colors, only on a terminal ----
if [[ -t 1 ]]; then
    C_OK=$'\e[32m'; C_ERR=$'\e[31m'; C_HEAD=$'\e[1m'; C_OFF=$'\e[0m'
else
    C_OK=""; C_ERR=""; C_HEAD=""; C_OFF=""
fi

die () {
    echo "${C_ERR}ERROR: $*${C_OFF}" >&2
    exit 1
}

banner () {
    echo ""
    echo "${C_HEAD}================================================================${C_OFF}"
    echo "${C_HEAD} $*${C_OFF}"
    echo "${C_HEAD}================================================================${C_OFF}"
}

step_ok () {
    echo "${C_OK}[$1] PASS${C_OFF} $2"
}

step_fail () {
    echo "${C_ERR}[$1] FAIL${C_OFF} $2" >&2
    exit 1
}

need_tool () {
    command -v "$1" >/dev/null 2>&1 || die "tool '$1' is not on the PATH. $2"
}

# ---- Configuration ----
CONFIG_FILE="$PROJ_DIR/config.sh"
[[ -f "$CONFIG_FILE" ]] || die "config.sh not found in $PROJ_DIR"
# shellcheck disable=SC1091
. "$CONFIG_FILE"

[[ -n "${DESIGN_NAME:-}" ]] || die "DESIGN_NAME is empty in config.sh"
[[ ${#RTL_FILES[@]} -gt 0 ]] || die "RTL_FILES is empty in config.sh"

# ================================================================
# Tool environment
#
# TOOL_ENV_FILES in section 0 of config.sh names the setup files of
# QuestaSim, Design Compiler, and PrimeTime. This part sources them, so
# every step finds its tool. It records each file in TOOL_ENV_FILES_USED,
# and 00_check.sh prints that list.
# ================================================================

TOOL_ENV_FILES_USED=()

# promote_root_on_path <install folder>
# It moves every folder of that install to the front of the PATH. A setup
# file adds its folders at the end, so a release that your shell holds
# already would win. This gives the release of TOOL_ENV_FILES the PATH.
promote_root_on_path () {
    local root="${1%/}" front="" rest="" dir
    [[ -n "$root" ]] || return 0
    local IFS=":"
    for dir in $PATH; do
        case "$dir" in
            "$root"|"$root"/*) front="${front:+$front:}$dir" ;;
            *)                 rest="${rest:+$rest:}$dir" ;;
        esac
    done
    [[ -n "$front" ]] && export PATH="$front:$rest"
    return 0
}

setup_tool_env () {
    local item file rc

    for item in "${TOOL_ENV_FILES[@]:-}"; do
        [[ -z "$item" ]] && continue
        case "$item" in
            /*) file="$item" ;;
            *)  file="$PROJ_DIR/$item" ;;
        esac
        [[ -r "$file" ]] || die \
"the setup file of TOOL_ENV_FILES is missing: $file
       Correct the path in section 0 of config.sh."
        if grep -qE '^[[:space:]]*setenv[[:space:]]' "$file" 2>/dev/null; then
            die \
"$file is a C shell file, and bash cannot read it.
       It sets variables with 'setenv', which bash does not know. Write its
       install folder into the matching file of tools/ instead."
        fi

        # A setup file may read an unset variable, so -u is off while it runs.
        set +u
        # shellcheck disable=SC1090
        . "$file"
        rc=$?
        # The file may leave a shell option behind, so the flow sets its own again.
        set -u
        set +e
        set -o pipefail
        cd "$PROJ_DIR"
        [[ $rc -eq 0 ]] || die \
"${file#$PROJ_DIR/} stopped the flow, and the message above names what to correct."
        TOOL_ENV_FILES_USED+=("$file")
    done

    # The setup files export the install folder of their tool, so the
    # release they name wins over the one your shell holds already.
    if [[ -n "${TOOL_ENV_FILES_USED[*]:-}" ]]; then
        promote_root_on_path "${MGC_QUESTA_HOME:-}"     # QuestaSim
        promote_root_on_path "${SYNOPSYS_SYN_ROOT:-}"   # Design Compiler
        promote_root_on_path "${SYNOPSYS:-}"            # PrimeTime
    fi

    # 00_check.sh reports the two license variables, so they get no note.
    [[ -n "${MGLS_LICENSE_FILE:-}" ]] && export MGLS_LICENSE_FILE
    [[ -n "${SNPSLMD_LICENSE_FILE:-}" ]] && export SNPSLMD_LICENSE_FILE
    return 0
}

setup_tool_env

# The message that every "tool is missing" error carries.
TOOL_HINT="Correct its install folder in its setup file, in tools/. Run ./00_check.sh."

# ---- Verification mode ----
VERIFY_MODE="${VERIFY_MODE:-sv}"
case "$VERIFY_MODE" in
    sv|cocotb) ;;
    *) die "VERIFY_MODE must be \"sv\" or \"cocotb\", and it is \"$VERIFY_MODE\"" ;;
esac

# ---- Defaults, so a short configuration file still works ----
TB_VERIFY="${TB_VERIFY:-tb_verify_${DESIGN_NAME}}"
TB_POWER="${TB_POWER:-tb_power_${DESIGN_NAME}}"
DUT_INSTANCE="${DUT_INSTANCE:-dut}"
COCOTB_TEST_MODULE="${COCOTB_TEST_MODULE:-test_${DESIGN_NAME}}"
COCOTB_TESTCASE="${COCOTB_TESTCASE:-}"

for _cfg_file in "${RTL_FILES[@]}"; do
    [[ -f "$PROJ_DIR/$_cfg_file" ]] || die "RTL file not found: $_cfg_file"
done
for _cfg_file in "${TB_EXTRA_FILES[@]:-}"; do
    [[ -z "$_cfg_file" ]] && continue
    [[ -f "$PROJ_DIR/$_cfg_file" ]] || die "TB_EXTRA_FILES entry not found: $_cfg_file"
done
unset _cfg_file

# ---- Technology ----
#
# TECH names the library. The default is the 15nm library. To run another
# one, set TECH in the environment, and send the results elsewhere so the
# two runs do not overwrite each other:
#
#     TECH=nangate45 RESULTS_DIR=$PWD/results_45 ./run_all.sh
#
# TECH_TIME_UNITS_PER_NS is the time unit of the library, as the number of
# units in one nanosecond. Design Compiler and PrimeTime read every SDC
# number in the time unit of the library, and config.sh states every time
# in nanoseconds, so the flow multiplies by this factor before it writes a
# constraint. If the factor is wrong, the tools accept the numbers without
# an error and report timing that is wrong by that factor. To confirm the
# value, read the time_unit line of the .lib file.
TECH="${TECH:-nangate15}"   # config.sh sets this

case "$TECH" in
    nangate15)
        TECH_NAME="NanGate 15nm"
        TECH_DIR="$PROJ_DIR/tech/nangate15"
        TECH_LIB="$TECH_DIR/NanGate_15nm_OCL_typical_conditional_nldm.lib"
        TECH_DB="$TECH_DIR/NanGate_15nm_OCL_typical_conditional_nldm.db"
        TECH_SIM_MODELS="$TECH_DIR/NanGate_15nm_OCL_functional.v"
        TECH_TIME_UNITS_PER_NS="1000"
        TECH_TIME_UNIT_NAME="ps"
        ;;
    nangate45)
        TECH_NAME="NanGate 45nm"
        TECH_DIR="$PROJ_DIR/tech/nangate45"
        TECH_LIB="$TECH_DIR/NangateOpenCellLibrary_typical.lib"
        TECH_DB="$TECH_DIR/NangateOpenCellLibrary_typical.db"
        TECH_SIM_MODELS="$TECH_DIR/NangateOpenCellLibrary.v"
        TECH_TIME_UNITS_PER_NS="1"
        TECH_TIME_UNIT_NAME="ns"
        ;;
    *)
        die "unknown TECH '$TECH'. Use nangate15 or nangate45."
        ;;
esac

[[ -f "$TECH_DB" ]] || die "compiled library not found: $TECH_DB"
[[ -f "$TECH_SIM_MODELS" ]] || die "cell simulation models not found: $TECH_SIM_MODELS"

# to_lib_time <nanoseconds> prints the same time in library time units.
# Every SDC number the flow writes passes through this function.
to_lib_time () {
    awk -v v="${1:-0}" -v f="${TECH_TIME_UNITS_PER_NS:-1}" 'BEGIN { printf "%.6g", v * f }'
}

# ---- Derived clock values ----
# The nanosecond values drive the simulators, because the testbenches carry
# a `timescale directive. The library values drive Design Compiler and
# PrimeTime. Never mix the two.
CLK_PERIOD_NS=$(awk -v f="${CLOCK_FREQ_MHZ:-500}" 'BEGIN { printf "%.4f", 1000.0 / f }')
CLK_HALF_NS=$(awk -v p="$CLK_PERIOD_NS" 'BEGIN { printf "%.4f", p / 2.0 }')
CLK_PERIOD_LIB=$(to_lib_time "$CLK_PERIOD_NS")
CLK_HALF_LIB=$(to_lib_time "$CLK_HALF_NS")

# ---- Output locations ----
RESULTS_DIR="${RESULTS_DIR:-$PROJ_DIR/results}"
VERIFY_DIR="$RESULTS_DIR/1_verify"
SYNTH_DIR="$RESULTS_DIR/2_synth"
VERIFY_SYN_DIR="$RESULTS_DIR/3_verify_syn"
POWER_DIR="$RESULTS_DIR/4_power"
NETLIST="$SYNTH_DIR/${DESIGN_NAME}_mapped.v"
VCD_FILE="$POWER_DIR/${DESIGN_NAME}.vcd"

# ---- Testbench file paths ----
tb_path () {
    local name="$1"
    if   [[ -f "$PROJ_DIR/tb/${name}.sv" ]]; then echo "$PROJ_DIR/tb/${name}.sv"
    elif [[ -f "$PROJ_DIR/tb/${name}.v"  ]]; then echo "$PROJ_DIR/tb/${name}.v"
    else return 1
    fi
}

# Absolute paths of the RTL sources.
rtl_abs_paths () {
    local item
    for item in "${RTL_FILES[@]}"; do echo "$PROJ_DIR/$item"; done
}

# Absolute paths of the extra testbench files.
tb_extra_abs_paths () {
    local item
    for item in "${TB_EXTRA_FILES[@]:-}"; do
        [[ -z "$item" ]] && continue
        echo "$PROJ_DIR/$item"
    done
}

# ---- Template rendering: replaces every @@KEY@@ with its value ----
# Usage: render <template> <output> KEY=value KEY=value ...
render () {
    local tmpl="$1" out="$2"; shift 2
    cp "$tmpl" "$out"
    local pair key val
    for pair in "$@"; do
        key="${pair%%=*}"
        val="${pair#*=}"
        VAL="$val" KEY="$key" perl -0pi -e 's/\@\@\Q$ENV{KEY}\E\@\@/$ENV{VAL}/g' "$out"
    done
}

# ---- PrimeTime report reading ----
# PrimeTime reports power in the unit of the library, and the power.tcl
# script writes that unit into units.rpt. This function returns the factor
# that converts a reported number into watts.
pt_power_scale () {
    local units="$POWER_DIR/units.rpt"
    [[ -f "$units" ]] || { echo 1; return; }
    awk '
        /[Pp]ower/ {
            if      ($0 ~ /mW/)          { print 1e-3;  found = 1; exit }
            else if ($0 ~ /uW|µW/)       { print 1e-6;  found = 1; exit }
            else if ($0 ~ /nW/)          { print 1e-9;  found = 1; exit }
            else if ($0 ~ /pW/)          { print 1e-12; found = 1; exit }
            else if ($0 ~ /W|[Ww]att/)   { print 1;     found = 1; exit }
        }
        END { if (!found) print 1 }' "$units"
}

# pt_watts <label> <report> [scale] prints the power of that line in watts.
# It reads a line of the form "<label> = <value> [<unit>]". A unit on the
# line wins. Without one, the scale argument applies, and it defaults to 1.
pt_watts () {
    [[ -f "$2" ]] || return 0
    awk -v lbl="$1" -v scale="${3:-1}" '
        index($0, lbl) && index($0, "=") {
            split($0, part, "=")
            n = split(part[2], f, /[ \t]+/)
            val = ""; unit = ""
            for (i = 1; i <= n; i++) {
                if (f[i] == "") continue
                if (val == "") { val = f[i] } else { unit = f[i]; break }
            }
            m = scale
            if      (unit ~ /^mW/) m = 1e-3
            else if (unit ~ /^uW/) m = 1e-6
            else if (unit ~ /^nW/) m = 1e-9
            else if (unit ~ /^pW/) m = 1e-12
            else if (unit ~ /^W/)  m = 1
            printf "%.6g", val * m
            exit
        }' "$2"
}

# format_mw <watts> prints the value in mW, or "n/a" for an empty input.
format_mw () {
    [[ -n "${1:-}" ]] || { echo "n/a"; return; }
    awk -v w="$1" 'BEGIN { printf "%.4g mW", w * 1000.0 }'
}

# make_work_lib <path> creates an empty QuestaSim work library.
#
# vlog creates the library itself when it is missing, but it calls vlib
# without quoting the path, so a project folder with a space in its name
# breaks the compile. vlib accepts the space, so the flow calls it first.
make_work_lib () {
    rm -rf "$1"
    vlib "$1" >/dev/null 2>&1 || die "could not create the QuestaSim work library: $1"
}

# ---- Common QuestaSim compile options ----
questa_defines () {
    echo "+define+CLK_PERIOD_NS=${CLK_PERIOD_NS}"
}

# ================================================================
# cocotb
#
# The steps use these functions when VERIFY_MODE is "cocotb". cocotb
# drives the design as the top level, so the same Python test runs on the
# RTL and on the gate-level netlist.
# ================================================================

PYTHON_BIN="${PYTHON_BIN:-python3}"

# Prints the folder that holds the cocotb makefiles.
cocotb_makefiles_dir () {
    local dir
    if command -v cocotb-config >/dev/null 2>&1; then
        dir=$(cocotb-config --makefiles 2>/dev/null) && { echo "$dir"; return 0; }
    fi
    dir=$("$PYTHON_BIN" -m cocotb_tools.config --makefiles 2>/dev/null) && { echo "$dir"; return 0; }
    dir=$("$PYTHON_BIN" -m cocotb.config --makefiles 2>/dev/null) && { echo "$dir"; return 0; }
    return 1
}

# Stops with an explanation when cocotb is not installed.
need_cocotb () {
    need_tool make "cocotb drives the simulator through a makefile."
    command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "PYTHON_BIN '$PYTHON_BIN' is not on the PATH."
    "$PYTHON_BIN" -c "import cocotb" 2>/dev/null || die \
"cocotb is not installed for $PYTHON_BIN.
       Install it with:  $PYTHON_BIN -m pip install cocotb
       Then set PYTHON_BIN in config.sh to that interpreter."
    cocotb_makefiles_dir >/dev/null || die "cocotb is installed, but its makefiles were not found."
}

# run_cocotb <rtl|gate> <output folder> [waves]
# It returns 0 when every test passes.
run_cocotb () {
    local level="$1" outdir="$2" waves="${3:-0}"
    local makefiles sources results build make_log
    makefiles=$(cocotb_makefiles_dir) || die "cocotb makefiles not found."

    build="$outdir/sim_build"
    results="$outdir/results.xml"
    make_log="$outdir/cocotb.log"
    rm -rf "$build" "$results"
    mkdir -p "$outdir"

    # ---- Source list ----
    sources=""
    if [[ "$level" == "gate" ]]; then
        sources="$TECH_SIM_MODELS $NETLIST"
    else
        local item
        while read -r item; do sources+="$item "; done < <(rtl_abs_paths)
    fi
    local extra
    while read -r extra; do sources+="$extra "; done < <(tb_extra_abs_paths)

    # ---- Compile options ----
    local compile_args="-sv +define+CLK_PERIOD_NS=${CLK_PERIOD_NS}"
    local gate_flag="0"
    if [[ "$level" == "gate" ]]; then
        compile_args+=" +define+GATE_LEVEL_SIM"
        gate_flag="1"
    fi
    if [[ ${#VLOG_EXTRA_ARGS[@]+x} ]] && [[ ${#VLOG_EXTRA_ARGS[@]} -gt 0 ]]; then
        compile_args+=" ${VLOG_EXTRA_ARGS[*]}"
    fi

    # Version 1 and version 2 of cocotb use different variable names.
    # Version 2 still accepts the old names, but it warns about each one.
    local ver major top_var module_var testcase_var
    ver=$("$PYTHON_BIN" -c "import cocotb; print(cocotb.__version__)" 2>/dev/null)
    major="${ver%%.*}"
    if [[ "${major:-1}" -ge 2 ]]; then
        top_var="COCOTB_TOPLEVEL"
        module_var="COCOTB_TEST_MODULES"
        testcase_var="COCOTB_TESTCASE"
    else
        top_var="TOPLEVEL"
        module_var="MODULE"
        testcase_var="TESTCASE"
    fi

    local testcase_arg=()
    [[ -n "${COCOTB_TESTCASE:-}" ]] && testcase_arg=("${testcase_var}=${COCOTB_TESTCASE}")

    echo "  cocotb        : ${ver:-unknown}"
    echo "  test module   : ${COCOTB_TEST_MODULE}"
    echo "  top level     : ${DESIGN_NAME}"

    # make runs inside the output folder, because QuestaSim writes its wave
    # file into the current folder. Every path handed to make is absolute.
    ( cd "$outdir" && \
      CLK_PERIOD_NS="$CLK_PERIOD_NS" \
      GATE_LEVEL_SIM="$gate_flag" \
      COCOTB_RESULTS_FILE="$results" \
      PYTHONPATH="$TB_DIR:${PYTHONPATH:-}" \
      make -f "$makefiles/Makefile.sim" \
        SIM=questa \
        TOPLEVEL_LANG=verilog \
        VERILOG_SOURCES="$sources" \
        "${top_var}=$DESIGN_NAME" \
        "${module_var}=$COCOTB_TEST_MODULE" \
        SIM_BUILD="$build" \
        COCOTB_RESULTS_FILE="$results" \
        COMPILE_ARGS="$compile_args" \
        WAVES="$waves" \
        "${testcase_arg[@]}" ) \
        2>&1 | tee "$make_log"

    local make_rc=${PIPESTATUS[0]}

    if [[ ! -f "$results" ]]; then
        echo "  cocotb wrote no results file. See $make_log"
        return 1
    fi
    if grep -q "<failure" "$results"; then
        grep -E "FAIL|Assertion" "$make_log" | head -20
        return 1
    fi
    return $make_rc
}
