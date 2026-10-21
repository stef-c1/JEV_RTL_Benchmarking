# PrimeTime power analysis script — NanGate 15nm Open Cell Library.
#
# Every path below is quoted, because the project folder may hold a space
# in its name. An unquoted path splits into several Tcl words.
#
# Every time value below arrives in the time unit of the library, which
# is 1ps for this library. 04_power.sh does the conversion.
#
# 04_power.sh renders this template into results/4_power/power.tcl.
# Edit this template, never the rendered copy.

set_app_var power_enable_analysis true
set_app_var power_analysis_mode averaged

# ---- Technology library ----
# The compiled .db file carries the internal power and the leakage tables,
# so PrimeTime reports all three power components, not the switching part
# alone.
set link_path    [list * "@@LIB_FILE@@"]
set link_library [list * "@@LIB_FILE@@"]
set power_dir    "@@POWER_DIR@@"

# ---- Gate-level netlist ----
read_verilog "@@NETLIST@@"
current_design @@DESIGN_NAME@@
link_design

# ---- Constraints ----
@@CLOCK_CMD@@
@@SDC_CONSTRAINTS@@

# ---- Switching activity from the gate-level simulation ----
read_vcd -strip_path "@@STRIP_PATH@@" "@@VCD_FILE@@"

# How much of the netlist the VCD annotates. A low number means the
# strip path or the testbench stimulus is wrong.
redirect -file "$power_dir/activity_check.rpt" { report_activity_annotation -verbose }

update_power

# ---- Reports ----
# The reports use the units of the library, so the flow records them.
redirect -file "$power_dir/units.rpt" { report_units }
redirect -file "$power_dir/power.rpt"           { report_power }
redirect -file "$power_dir/power_hierarchy.rpt" { report_power -hierarchy }
redirect -file "$power_dir/power_by_cell.rpt"   { report_power -cell_power -nworst 20 }

report_power

exit
