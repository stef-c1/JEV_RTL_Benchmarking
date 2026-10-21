#!/usr/bin/bash
#
# config.sh — the only file you edit.
#
# Section 0 sets up the tools. The install folders live in the files of
# tools/, one file per tool release, and section 0 only names the three
# files the flow reads.
#
# As it stands it runs the example design, mac_int8, so the flow works
# before you change anything.
#
# For your own design: put your files next to the example files, in rtl/
# and tb/, then change section 1 and section 2 below. Run ./00_check.sh
# after every change, because it names each mistake it finds.
#
# Every path is relative to this folder.
#

# ================================================================
# 0. TOOL ENVIRONMENT
#
# The flow needs QuestaSim (vlog, vsim), Design Compiler (dc_shell), and
# PrimeTime (pt_shell). The tools/ folder holds one setup file per tool
# release, and the three files below are the release the flow was tested
# with. The flow sources them, in this order, before it starts a tool.
#
# To use another release, name its file here. The tools/ folder also holds
# the 2024.09 release of the two Synopsys tools:
#     "tools/syn_vW-2024.09-SP5.rc"
#     "tools/pt_vW-2024.09-SP5.rc"
#
# If a tool sits somewhere else on your machine, open its file and correct
# every install folder in it. One line holds it for QuestaSim and for
# PrimeTime, and four lines for Design Compiler. See tools/README.md.
#
# Your shell may set the tools up already, as it does at ESAT. The flow
# then puts the release named here first, so the list decides. Empty the
# list when you want the PATH of your shell and nothing else.
# ================================================================

TOOL_ENV_FILES=(
    "tools/questasim_2022.4.rc"
    "tools/syn_vU-2022.12-SP2.rc"
    "tools/pt_vU-2022.12-SP2.rc"
)

# The license servers, as "port@host". The three files above set them, and
# a value here wins over that.
MGLS_LICENSE_FILE="${MGLS_LICENSE_FILE:-}"        # QuestaSim
SNPSLMD_LICENSE_FILE="${SNPSLMD_LICENSE_FILE:-}"  # Design Compiler and PrimeTime

# ================================================================
# 1. DESIGN
# ================================================================

# The technology library. Two are bundled, in tech/:
#   "nangate15"   NanGate 15nm Open Cell Library, 0.8 V, 25 C  (the default)
#   "nangate45"   NanGate 45nm Open Cell Library, 1.1 V, 25 C
#
# The two libraries state time in different units, and common.sh converts
# every constraint for you, so change this line and nothing else. To run
# both without overwriting the results, name a results folder per run:
#   TECH=nangate45 RESULTS_DIR=$PWD/results_45 ./run_all.sh
TECH="${TECH:-nangate15}"

# The name of the top module, as written in the RTL. Not the file name.
DESIGN_NAME="mac_int8"

# The clock port of the top module. Use "" for a combinational design.
CLOCK_PORT="clk_i"

# The frequency you synthesize for. Set CLOCK_FREQ_MHZ in the environment
# to override this value for one run, which is how you sweep a frequency:
#     CLOCK_FREQ_MHZ=1500 RESULTS_DIR=$PWD/results_1500 ./02_synth.sh
CLOCK_FREQ_MHZ="${CLOCK_FREQ_MHZ:-500}"

# Every RTL file of the design, in dependency order: a module comes after
# the modules it uses, so the top module is last. Add one line per file.
# The example is three files, and mac_int8 uses the other two.
RTL_FILES=(
    "rtl/mult_signed8.v"
    "rtl/acc_signed32.v"
    "rtl/mac_int8.v"
)

# ================================================================
# 2. TESTBENCHES
#
# Both testbenches are files in tb/. The file name, without the
# extension, is the module name. See tb/README.md for the rules.
# ================================================================

# The verification testbench. It must print "ALL TESTS PASSED" when it passes.
TB_VERIFY="tb_verify_mac_int8"

# The power testbench. It must write a VCD file.
TB_POWER="tb_power_mac_int8"

# The instance name of your design inside both testbenches. PrimeTime maps
# the VCD onto the netlist with the path <TB_POWER>/<DUT_INSTANCE>, so a
# wrong name here gives a power of zero.
DUT_INSTANCE="dut"

# ================================================================
# 3. VERIFICATION WITH cocotb (optional)
#
# Set VERIFY_MODE="cocotb" to run the Python tests in tb/ instead of the
# SystemVerilog testbench. Steps 1 and 3 then use tb/test_mac_int8.py.
# Step 4 always uses TB_POWER above.
# ================================================================

VERIFY_MODE="sv"

# The Python test file in tb/, without the .py extension.
COCOTB_TEST_MODULE="test_mac_int8"

# One test function to run. "" runs every test in the file.
COCOTB_TESTCASE=""

# The Python interpreter that has cocotb installed.
PYTHON_BIN="python3"

# ================================================================
# 4. SETTINGS YOU RARELY CHANGE
# ================================================================

# Files that only the testbenches need, such as a memory image or a
# package. The flow compiles them, and never synthesizes them.
TB_EXTRA_FILES=(
)

# Design Compiler compile_ultra flags.
#   -gate_clock      : insert clock gates to reduce dynamic power
#   -retime          : allow registers to move through combinational logic
#   -no_auto_ungroup : keep the module hierarchy (if you want power and area split up by module)
COMPILE_FLAGS="-gate_clock"

# I recommend keeping these default values.
#
# State every time here in nanoseconds, whatever the technology. The
# library states time in its own unit, which is 1ps for NanGate 15nm and
# 1ns for NanGate 45nm. common.sh converts each value before it writes an
# SDC command, so you never write a picosecond here.
MAX_TRANSITION="0.250"          # ns
MAX_FANOUT="32"
CLK_UNCERTAINTY_SETUP="0.05"    # ns
CLK_UNCERTAINTY_HOLD="0.025"    # ns
# The input and output delay, as a fraction of the clock period.
IO_DELAY_FRACTION="0.1"

# The load on each output port, in femtofarad. Both libraries state
# capacitance in femtofarad, so this value needs no conversion.
#
# Empty means the outputs drive nothing. Synthesis then reports the area and
# the power of a design with no load, which is optimistic, and Design
# Compiler has little reason to choose a stronger cell. Set a value near the
# load your outputs really see, such as "20".
OUTPUT_LOAD_FF="${OUTPUT_LOAD_FF:-}"

# The cell that drives each input port, such as "BUF_X4". Both libraries
# hold that cell. Empty means the inputs come from an ideal source with no
# transition time, which is optimistic in the same way.
DRIVING_CELL="${DRIVING_CELL:-}"

# Extra arguments for the QuestaSim compiler. Empty is right for most
# designs, because the testbenches carry their own `timescale directive.
# Add one of these when your design needs it:
#   "+incdir+rtl/include"   a search path for `include files
#   "+define+WIDTH=16"      a compile-time macro your RTL reads
#   "-timescale 1ns/1ps"    a default for RTL without a `timescale directive
#   "-suppress 2286"        silences one warning number
VLOG_EXTRA_ARGS=(
)

VSIM_EXTRA_ARGS=(
)
