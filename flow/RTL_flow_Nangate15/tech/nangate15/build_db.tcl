# Compiles the Liberty source into the .db form that Design Compiler and
# PrimeTime read. Run it with:  lc_shell -f build_db.tcl
set lib_src  NanGate_15nm_OCL_typical_conditional_nldm.lib
set lib_name NanGate_15nm_OCL
set lib_out  NanGate_15nm_OCL_typical_conditional_nldm.db

read_lib  $lib_src
write_lib $lib_name -format db -output $lib_out
exit
