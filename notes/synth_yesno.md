# synth_yesno: Does the design synthesize?

## Goal

Measure if the model can tell whether Design Compiler (DC) synthesizes a design to a complete
gate-level netlist. The answer is the answer of the tool, not the answer of a textbook. These two
answers are different for several constructs (see "Trap subset").

## Question

- Jev type: `noul`.
- Instruction (draft): "Does the tool in `tool` synthesize the module `top` in `rtl` to a complete
  gate-level netlist?"
- Criteria:
  - true: "The tool finishes with no error, every module instance is resolved, and every register
    maps to a library cell."
  - false: "The tool stops with an error, or a module instance is not resolved, or a register cannot
    map to a library cell."

## State

| Field | Content |
|---|---|
| `rtl` | All source files, top module last. |
| `top` | The name of the top module. |
| `tool` | "Synopsys Design Compiler U-2022.12-SP2 (analyze -format sverilog, elaborate, link, compile_ultra), NanGate 15nm Open Cell Library." |

## Correct answer

Run step 2 of the flow (`02_synth.sh`). The design synthesizes only if all four conditions are true:

1. The DC log has no line that starts with `Error:`.
2. The DC log has no unresolved reference: no warning LINK-5 ("Unable to resolve reference") and no
   warning UID-341 ("has unresolved references").
3. The DC log has no warning TRANS-4 ("Target library contains no replacement for register ...
   (**FFGEN**)").
4. DC writes the netlist.

After a failed design, MV's flow continues its script. The constraint and report commands then add
the follow-on errors CMD-036, UID-22, UID-109, and UID-4. They do not show a class
(harness/synthcheck.py).

`02_synth.sh` checks conditions 1 and 4 only. The probes show that conditions 2 and 3 are necessary:

- Probe `p03_missing_module` instantiates a module that does not exist. DC gives the warnings LINK-5
  and UID-341, keeps the instance as a black box, and writes a netlist with 10.22 um2 of cells.
- Probe `p27_async_data_load` resets a register to a data input, not to a constant. DC gives the
  warning TRANS-4 for each bit, and the netlist keeps generic `**FFGEN**` registers.

If DC reports SEC-50 (no free license), the run is not a result. Wait and run it again.

## The probe results

`probes/synth_classes.py` runs 51 small probe modules through QuestaSim `vlog` and DC. The results are
in `probes/synth_classes_results.csv` (run on 2026-10-09 with DC U-2022.12-SP2). The summary:

| DC result | Probes |
|---|---|
| Synthesizes, no special message | clean accumulator, latch, combinational loop (DC disables one timing arc), division by a variable, continuous assignment to a `reg` variable, `$display`, data-dependent `while` loop, `for` loop with a variable bound, `repeat` with a variable count, two `@(posedge clk)` controls in one block, hierarchical reference `u0.r`, `always` with no event control |
| Synthesizes, DC ignores the construct with a warning | `initial` (VER-281), `#` delay statement (VER-176), intra-assignment delay (VER-130), delay on `assign` (VER-173), `$fopen` (VER-274), comparison with `x` (ELAB-310) |
| Netlist, but not complete (synth_yesno answer: false) | missing module (LINK-5, UID-341), reset to a data value (TRANS-4) |
| DC error (synth_yesno answer: false) | 30 probes, see the class table in synth_reason.md |

## Main set

- 250 designs with the answer true and 250 designs with the answer false.
- The false designs are the mutants of synth_reason (25 of each class). The true designs are the base designs
  of these mutants, plus other clean designs. Thus most false designs have a true twin that differs
  in one construct only.
- Do not put designs from the row "DC ignores the construct with a warning" in the main set. For
  these designs, the textbook answer and the tool answer are different, so they go in the trap subset.

## Trap subset

The trap subset has 100 extra questions (50 pairs). Each pair holds two near-identical designs. DC
synthesizes one design and rejects the other. A common rule of thumb gives the same answer for both.
The harness makes the first three kinds of the table now (`#2` delay, `$display`, `initial`). The
other three kinds are not yet implemented.

| DC synthesizes (true) | DC rejects (false) |
|---|---|
| `#2` delay statement (ignored) | `wait` statement (VER-188) |
| `$display` or `$fopen` (ignored) | `$random` (ELAB-939) |
| `while (x != 0)` loop with a data-dependent end | `forever` loop with no timing control (ELAB-900) |
| two `@(posedge clk)` controls in one block | `@(posedge clk)` and then `@(negedge clk)` in one block (ELAB-407) |
| asynchronous reset to a constant | asynchronous reset to a data value (TRANS-4) |
| `initial` block (ignored) | `force` and `release` (VER-967, VER-968) |

Report the trap subset separately from the main set. It shows if the model knows what DC does, or
only a rule of thumb.

## Designs

- Base designs: VerilogEval reference solutions, RTLLM verified designs, REvolution v0 designs, and
  Orchestrator variants. Each base design must synthesize under the four conditions above.
- Natural failures: DC logs of LLM-written RTL. A search of 100 s in the Orchestrator logs found the
  error VER-216 ("ACC_W is not a parameter in module mac_accum"). Add natural failures where they
  exist, and mark them.

## Controls

- R, M, U, and P from README.md.
- Example for M on a false design: `// checked: DC compile is clean`. Example on a true design:
  `// TODO: DC rejects this block`.
- The unrelated modules of U must synthesize themselves, so they do not change the answer.
- O does not apply (noul).

## Metrics

- The noul metrics from README.md.
- The recall of the false answer for each synth_reason class. This shows which classes the model misses.
- The accuracy on the trap subset, separately for the true side and the false side.

## Open points

1. Confirm that designs with ignored constructs (`initial`, `#` delays, `$display`) count as
   synthesizable, as DC treats them.
