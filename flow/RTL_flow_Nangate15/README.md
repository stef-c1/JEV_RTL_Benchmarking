# EXPORT_RTL_Synthesis

Takes RTL and testbenches through verification, synthesis, post-synthesis
verification, and power analysis. The NanGate 15nm Open Cell Library is
bundled in `tech/nangate15/`. Nothing outside this folder is needed.

## Start

The folder holds a working example, an int8 multiply-accumulate unit. Run it
before you add your own design.

```bash
cd EXPORT_RTL_Synthesis
./00_check.sh           # checks the setup, starts no tool
./run_all.sh            # the four steps, then the summary
```

If `./00_check.sh` reports a tool that is not on the `PATH`, correct its setup
file in `tools/`, as the next part describes.

## The path must hold no space

Put the flow in a folder whose full path holds no space. Design Compiler
splits its library variables on every space, whatever the quoting, and it
then stops with an internal error. QuestaSim has the same fault in `vlog`.
`./00_check.sh` tests the path and names the problem.

A symbolic link without a space also works, because the flow reads the path
you start it from:

```bash
ln -s "/users/micas/scuycken/Master Thesis of students/RTL_flow_FreePDK15" ~/rtl_flow_freepdk15
cd ~/rtl_flow_freepdk15 && ./run_all.sh
```

## The technology

The flow maps to the NanGate 15nm Open Cell Library, at the typical corner of
0.8 V and 25 degrees Celsius. The library states time in picoseconds, and
`config.sh` states time in nanoseconds, so `common.sh` converts every time
value before it writes a constraint. `TECH_TIME_UNITS_PER_NS` holds the
factor. To go back to the 45nm library, point `TECH_DIR`, `TECH_LIB`,
`TECH_DB`, and `TECH_SIM_MODELS` in `common.sh` at the files in
`tech/nangate45/`, set `TECH_TIME_UNITS_PER_NS` to 1, and set
`TECH_TIME_UNIT_NAME` to `ns`. See `tech/nangate15/README.md`.

## The tool environment

The flow needs QuestaSim (`vlog`, `vsim`), Design Compiler (`dc_shell`), and
PrimeTime (`pt_shell`). The `tools/` folder holds one setup file per tool
release, and the flow sources three of them before it starts a tool, so your
shell needs no setup of its own. Section 0 of `config.sh` names the three:

```bash
TOOL_ENV_FILES=(
    "tools/questasim_2022.4.rc"
    "tools/syn_vU-2022.12-SP2.rc"
    "tools/pt_vU-2022.12-SP2.rc"
)
```

That is the release the flow was tested with. To use another one, change a
file name in the list, and `tools/` also holds `syn_vW-2024.09-SP5.rc` and
`pt_vW-2024.09-SP5.rc`. A setup file adds its folders at the end of the
`PATH`, so a shell that holds another release already would win. The flow
moves the folders of the release you name to the front, and `./00_check.sh`
prints the full path of each tool it found, so you see which one runs.

When a tool sits somewhere else on your machine, open its file in `tools/` and
correct the install folder in it. `tools/README.md` names the lines that hold
it, one line for QuestaSim and PrimeTime, and four for Design Compiler.
Empty the list when you want the `PATH` of your shell and nothing else.

## The four steps

Each command stops at the first error.

| Command | Tool | Result |
| --- | --- | --- |
| `./00_check.sh` | none | Reports mistakes in the configuration, the files, and the tools. |
| `./01_verify.sh` | QuestaSim | Simulates the RTL against the verification testbench. |
| `./02_synth.sh` | Design Compiler | Maps the RTL to NanGate 15nm. Writes the netlist, the area, and the timing. |
| `./03_verify_syn.sh` | QuestaSim | Runs the verification testbench on the gate-level netlist. |
| `./04_power.sh` | QuestaSim, PrimeTime | Simulates the power testbench on the netlist, then reports the power. |

`./run_all.sh` runs the check and the four steps. `./summary.sh` prints area,
slack, and power in one table. `./clean.sh` deletes everything the flow
wrote.

## The example design

```
mac_int8                rtl/mac_int8.v         the top module
  mult_signed8          rtl/mult_signed8.v     signed 8-bit multiplier
  acc_signed32          rtl/acc_signed32.v     accumulator, enable and clear
```

`RTL_FILES` in `config.sh` lists all three. A module comes after the modules
it uses, so the top module is last.

```bash
RTL_FILES=(
    "rtl/mult_signed8.v"
    "rtl/acc_signed32.v"
    "rtl/mac_int8.v"
)
```

`./00_check.sh` warns when the top module is not last.

## Your own design

Put your files in `rtl/` and `tb/`, next to the example files. Change these
lines in `config.sh`:

```bash
DESIGN_NAME="my_design"                 # the top module, not the file name
CLOCK_PORT="clk_i"                      # "" for a combinational design
CLOCK_FREQ_MHZ=400                      # the frequency you synthesize for
RTL_FILES=(                             # every file, top module last
    "rtl/my_adder.v"
    "rtl/my_control.v"
    "rtl/my_design.v"
)
TB_VERIFY="tb_verify_my_design"         # the file name, without .sv
TB_POWER="tb_power_my_design"           # the file name, without .sv
DUT_INSTANCE="dut"                      # the instance name in both testbenches
```

Run `./00_check.sh`, fix what it reports, then run `./run_all.sh`.

`config.sh` decides which files the flow reads, so the example files can
stay. A file that only the testbench needs, such as a memory image or a
package, goes in `TB_EXTRA_FILES` and is never synthesized.

## What the testbenches must do

`tb/README.md` has the detail.

1. The verification testbench prints `ALL TESTS PASSED` when every check
   passes. Steps 1 and 3 search for that text.
2. The power testbench writes a VCD file with `$dumpfile` and `$dumpvars`.
   The simulator runs inside `results/4_power/`, so a plain file name lands
   there.

The flow sets two macros: `` `CLK_PERIOD_NS ``, and `` `GATE_LEVEL_SIM `` in
the gate-level runs. Guard both with `` `ifndef ``, so the file also compiles
outside the flow.

## Verification with cocotb

`VERIFY_MODE="cocotb"` in `config.sh` runs the Python tests in
`tb/test_mac_int8.py` in steps 1 and 3, instead of the SystemVerilog
testbench. cocotb drives the design as the top level, so one test file
checks the RTL in step 1 and the netlist in step 3. Step 4 keeps the
SystemVerilog power testbench.

```bash
python3 -m pip install --user cocotb
```

Install it for the interpreter in `PYTHON_BIN`. Version 1.9 and version 2.0
both work.

## Folder layout

```
config.sh          the only file you edit
tools/             one setup file per tool release, see tools/README.md
rtl/               the RTL, the example (three files) and yours
tb/                the testbenches, the example and yours
spec/              the design specification
results/           everything the flow writes

00_check.sh 01_verify.sh 02_synth.sh 03_verify_syn.sh 04_power.sh
run_all.sh summary.sh clean.sh
common.sh          shared setup, the steps source it
scripts/           the Design Compiler and PrimeTime templates
tech/nangate15/    the bundled NanGate 15nm library
tech/nangate45/    the NanGate 45nm library, kept for comparison
```

## Results

```
results/
  1_verify/      compile.log, sim.log
  2_synth/       <design>_mapped.v, <design>.sdc, area.rpt, timing.rpt,
                 qor.rpt, violations.rpt, synth.log
  3_verify_syn/  compile.log, sim.log
  4_power/       <design>.vcd, power.rpt, power_hierarchy.rpt,
                 activity_check.rpt, units.rpt, pt.log
  summary.txt    area, slack, and power in one table
  summary.csv    the same numbers as one row
```

## The numbers

- The area comes from `report_area` after `compile_ultra`, in um2.
- The worst slack is the margin of the critical path at the frequency in
  `config.sh`, and it comes from `report_qor`. A positive slack means the
  path arrives early, so the design holds that frequency, and the summary
  says `MET`. A negative slack carries a minus sign, the design misses the
  frequency, and the summary says `VIOLATED`. Lower `CLOCK_FREQ_MHZ` and
  synthesize again. The frequency the summary names after the verdict is the
  critical path of this run, so synthesis at that frequency gives another
  netlist and another number.
- `results/2_synth/qor.rpt` holds the total negative slack and the number of
  violating paths, and `results/2_synth/violations.rpt` lists every path that
  misses its constraint. Both are empty for a design that meets timing.
- The power comes from PrimeTime, with the switching activity of the power
  testbench annotated onto the netlist. The stimulus sets the dynamic power,
  so the workload is part of the result.
- The cell models have no delays. Step 3 checks function, and the timing
  result is the slack from step 2.
- `compile_ultra` flattens the hierarchy. Add `-no_auto_ungroup` to
  `COMPILE_FLAGS` for per-module area and power.

## Requirements

QuestaSim (`vlog`, `vsim`), Design Compiler (`dc_shell`), and PrimeTime
(`pt_shell`), plus a license for each. The files in `tools/` hold their
install folders, and the tool environment above describes how to point them
somewhere else. `./00_check.sh` reports a tool that is missing. cocotb and
`make` are needed for `VERIFY_MODE="cocotb"` only.
