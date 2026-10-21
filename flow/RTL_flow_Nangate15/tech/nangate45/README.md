# NanGate 45nm Open Cell Library

The flow uses these three files, and needs no other technology data.

| File | Used by | Purpose |
| --- | --- | --- |
| `NangateOpenCellLibrary_typical.db` | Design Compiler, PrimeTime | Timing and power data, typical corner, in the compiled form both tools read. |
| `NangateOpenCellLibrary.v` | QuestaSim | Behavioral models of the 135 cells, for the gate-level simulations of steps 3 and 4. |
| `NangateOpenCellLibrary_typical.lib` | nothing in the flow | The Liberty source of the .db file. Kept for reference, and to rebuild the .db with `lc_shell` if a future tool version rejects it. |

## Corner

The typical corner: 1.10 V, 25 degrees Celsius.

## The .db file

Design Compiler and PrimeTime read the compiled `.db` form, not the Liberty
text. The file is bundled, so the flow builds nothing.

## The simulation models

The models have no delays. A gate-level simulation with them therefore checks
function only, and the timing result comes from the static timing analysis in
`results/2_synth/timing.rpt`.

## Origin

The library is the NanGate 45nm Open Cell Library (Copyright 2004-2011 Nangate
Inc.), an open library for research and teaching. The Verilog models were
generated from the Liberty file.
