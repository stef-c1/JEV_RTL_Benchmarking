# NanGate 15nm Open Cell Library

The flow uses these three files, and needs no other technology data.

| File | Used by | Purpose |
| --- | --- | --- |
| `NanGate_15nm_OCL_typical_conditional_nldm.db` | Design Compiler, PrimeTime | Timing and power data, typical corner, in the compiled form both tools read. |
| `NanGate_15nm_OCL_functional.v` | QuestaSim | Behavioral models of the 76 cells, for the gate-level simulations of steps 3 and 4. |
| `NanGate_15nm_OCL_typical_conditional_nldm.lib` | `build_db.tcl` | The Liberty source of the .db file. |

## Corner

The typical corner: 0.8 V, 25 degrees Celsius, high performance (HP) process.

## The time unit

The library states time in picoseconds. The 45nm library states time in
nanoseconds. Design Compiler and PrimeTime read every SDC number in the unit
of the library, so the flow converts each time value before it writes a
constraint. `TECH_TIME_UNITS_PER_NS` in `common.sh` holds the factor, and it
is 1000 for this library.

This matters. If the factor is wrong, both tools accept the numbers without
an error and report timing that is wrong by a factor of 1000.

The power units also differ: this library states leakage in picowatts, and
the 45nm library states it in nanowatts. The flow reads the unit from the
`units.rpt` report that PrimeTime writes, so `summary.sh` needs no change.

## The .db file

Design Compiler and PrimeTime read the compiled `.db` form, not the Liberty
text. The file is bundled, so the flow builds nothing. To rebuild it:

```bash
source ../../tools/syn_vU-2022.12-SP2.rc
lc_shell -f build_db.tcl
```

Library Compiler prints warnings about the `FILL`, `FILLTIE`, and `ANTENNA`
cells, which carry no logic function, and about negative internal power
values in a few tables. Both are normal for this library, and neither stops
the compilation.

## The simulation models

The models have no delays. A gate-level simulation with them therefore checks
function only, and the timing result comes from the static timing analysis in
`results/2_synth/timing.rpt`.

The package also holds `NanGate_15nm_OCL_conditional.v`, which adds specify
blocks with timing checks. The flow does not use it, because the flow
back-annotates no SDF file, and the checks would report violations that mean
nothing.

## The cells

The library holds 76 cells, against 135 in the 45nm library. It carries four
flip-flops: `DFFRNQ_X1` and `DFFSNQ_X1`, plus a scan version of each. Every
flip-flop has one drive strength and a Q output with no QN output. Design
Compiler therefore has fewer choices than at 45nm, so expect a different area
and timing result, not a scaled one.

`CLKGATETST_X1` is the integrated clock gating cell, of type
`latch_posedge_precontrol`. The `-gate_clock` flag in `config.sh` uses it.

## Origin and license

The library is the NanGate 15nm Open Cell Library, built by Nangate Inc. on
the NCSU FreePDK15 process. Silvaco, which acquired Nangate, released it to
the Silicon Integration Initiative (Si2) under the Apache 2.0 license. See
`LICENSE.txt` and `NOTICE.txt`. Universities obtain the complete package from
https://si2.org/open-cell-library/

The file headers inside the `.lib` and `.v` files still carry the Nangate
copyright text from 2014, which mentions a restrictive license agreement.
That text is old. The Apache 2.0 license in `LICENSE.txt` governs this copy.

The FreePDK15 process kit itself (`freepdk15-v12.tar` in the project root)
holds the Virtuoso technology library, the Calibre rule decks, and the HSPICE
device models. It holds no cells, so this flow does not read it. Keep it for
a later place and route step.
