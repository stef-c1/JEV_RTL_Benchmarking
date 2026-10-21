#!/usr/bin/bash
#
# Removes every generated file. The RTL, the testbenches, the
# specifications, and the technology files stay.
#
# Usage:  ./clean.sh
#

PROJ_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$PROJ_DIR"

rm -rf results
rm -rf work modelsim.ini transcript vsim.wlf *.vcd
rm -rf alib-* default.svf command.log *.log *.svf .synopsys_dc.setup_cache

echo "Removed the results folder and the tool leftovers."
