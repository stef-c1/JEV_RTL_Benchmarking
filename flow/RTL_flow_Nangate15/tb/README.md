# Testbenches

Your testbenches go in this folder, next to the example files. Each file
holds one module, and the file name without the extension is the module
name. Name the two files in `config.sh`.

The example is `tb_verify_mac_int8.sv` and `tb_power_mac_int8.sv`.

## The verification testbench

Steps 1 and 3 run it. Step 1 compiles it with the RTL, step 3 with the
gate-level netlist.

- It must print `ALL TESTS PASSED` when every check passes. The step
  searches for that text, and fails without it.
- It must end with `$finish`. Add a watchdog that stops a run that hangs.
- It must drive every input of the design before the reset ends. An
  undriven input is X. The RTL run can pass with X values, and the
  gate-level run of step 3 then fails.

## The power testbench

Step 4 runs it on the gate-level netlist and reads the VCD file it writes.

- It must call `$dumpfile("power.vcd")` and `$dumpvars(0, <the module name
  of the testbench>)`. The simulator runs inside `results/4_power/`, so the
  file lands there. The flow renames it after the design.
- The stimulus must be the workload whose power you want. The switching
  activity in the VCD file sets the dynamic power.
- It must start the dump after the reset, and end with `$finish`.

## The instance name

Both testbenches must instantiate the design with the name in
`DUT_INSTANCE`. PrimeTime maps the VCD file onto the netlist with the path
`<TB_POWER>/<DUT_INSTANCE>`. A wrong name gives a power of zero, and
`./00_check.sh` catches it.

## The macros the flow sets

| Macro | Value | Set in |
| --- | --- | --- |
| `` `CLK_PERIOD_NS `` | the clock period in ns | every step |
| `` `GATE_LEVEL_SIM `` | defined, no value | steps 3 and 4 |

Guard both with `` `ifndef ``, so the testbench also compiles outside the
flow.

## cocotb tests

`VERIFY_MODE="cocotb"` in `config.sh` runs the Python file named in
`COCOTB_TEST_MODULE` in steps 1 and 3, instead of the SystemVerilog
testbench. `test_mac_int8.py` is the example, and it checks the same
behavior as `tb_verify_mac_int8.sv`.

- The design is the top level. A test reaches the ports as
  `dut.<port name>`. There is no testbench module, and `DUT_INSTANCE` does
  not apply.
- The same file runs on the RTL and on the netlist. The environment
  variable `GATE_LEVEL_SIM` is `1` in the gate-level run.
- The environment variable `CLK_PERIOD_NS` holds the clock period.
- A test fails through an ordinary `assert`.

## Extra files

A testbench that needs a memory image, a reference model, or a package
lists those files in `TB_EXTRA_FILES` in `config.sh`. The flow compiles them
before the testbench, and never synthesizes them.
