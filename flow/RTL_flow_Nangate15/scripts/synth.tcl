# Design Compiler synthesis script — NanGate 15nm Open Cell Library.
#
# Every time value below arrives in the time unit of the library, which
# is 1ps for this library. 02_synth.sh does the conversion.
#
# Every path below is quoted, because the project folder may hold a space
# in its name. An unquoted path splits into several Tcl words.
#
# 02_synth.sh renders this template into results/2_synth/synth.tcl.
# Edit this template, never the rendered copy.

# ---- Technology library ----
set target_library [list "@@LIB_FILE@@"]
set link_library   [list * "@@LIB_FILE@@"]
set synth_dir      "@@SYNTH_DIR@@"

# ---- Read the RTL ----
@@ANALYZE_CMDS@@

# ---- Elaborate the top module ----
elaborate @@DESIGN_NAME@@
current_design @@DESIGN_NAME@@
link

# ---- Constraints ----
@@CLOCK_CMD@@
@@SDC_CONSTRAINTS@@

# ---- Compile ----
compile_ultra @@COMPILE_FLAGS@@

# ---- Reports ----
redirect -file "$synth_dir/area.rpt"            { report_area }
redirect -append -file "$synth_dir/area.rpt"    { report_area -hierarchy }
redirect -file "$synth_dir/timing.rpt"          { report_timing -max_paths 5 -significant_digits 4 }
redirect -file "$synth_dir/qor.rpt"             { report_qor }
redirect -file "$synth_dir/power_estimate.rpt"  { report_power -analysis_effort low }
redirect -file "$synth_dir/violations.rpt"      { report_constraint -all_violators }

# The reports use the units of the library, so the flow records them.
redirect -file "$synth_dir/units.rpt"           { report_units }

# ---- Write the gate-level netlist ----
change_names -rules verilog -hierarchy
write -format verilog -hierarchy -output "$synth_dir/@@DESIGN_NAME@@_mapped.v"
write_sdc "$synth_dir/@@DESIGN_NAME@@.sdc"

exit
