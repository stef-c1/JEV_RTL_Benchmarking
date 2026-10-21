# synth_reason: Why does the design not synthesize?

## Goal

Measure if the model can find the reason why Design Compiler (DC) does not synthesize a design. Each
design in this test fails synth_yesno for exactly one reason. The model selects that reason from 10 classes.

## Question

- Jev type: `choice`, 10 options.
- Instruction (draft): "The tool in `tool` does not synthesize the module `top` in `rtl` to a
  complete gate-level netlist. Select the reason."
- State: the same fields as synth_yesno (`rtl`, `top`, `tool`).
- Options (label: description):

| # | Label | Description (draft) |
|---|---|---|
| 1 | `illegal_code` | The code is not legal Verilog or SystemVerilog: a syntax error, an undeclared name, a non-constant range, or a procedural assignment to a net. |
| 2 | `unsupported_construct` | The code is legal for a simulator, but it uses a data type or construct that synthesis does not support: `real`, `time`, `string`, `trireg`, a class, a dynamic array, a DPI import, or a user-defined primitive. |
| 3 | `timing_control` | The code uses a timing control that synthesis does not support: `wait`, `fork`-`join`, or an event trigger (`->`). |
| 4 | `simulation_statement` | The code uses a statement or system function for simulation only: `force`-`release`, procedural `assign`-`deassign`, or `$random`. |
| 5 | `event_list` | An event list that synthesis does not support: both edges of one signal, edge and level events mixed, or different edges in one process. |
| 6 | `async_reset` | An asynchronous reset or set that synthesis cannot build: statements outside the reset `if`-`else`, a second edge signal without the reset template, or a reset to a non-constant value. |
| 7 | `multiple_drivers` | A signal has more than one driver, for example assignments in two `always` blocks. |
| 8 | `mixed_assignments` | One variable gets blocking and nonblocking assignments in the same `always` block. |
| 9 | `unbounded_loop` | A loop or a recursion that synthesis cannot unroll: a `forever` loop with no timing control, or a recursion with no constant limit. |
| 10 | `instance_mismatch` | A module instance does not match a module: a missing module, an unknown parameter, or an unknown port. |

## Correct answer

The class comes from the DC message ID, with the `vlog` result for class 1 and class 2. The table
shows the IDs that the probes produced (`probes/synth_classes_results.csv`, DC U-2022.12-SP2,
2026-10-09).

| # | Class | DC message IDs | `vlog` | Probes |
|---|---|---|---|---|
| 1 | `illegal_code` | VER-294, VER-956, VER-260, VER-952 | error | `p01`, `p02`, `p36`, `p23` |
| 2 | `unsupported_construct` | VER-177, VER-191, VER-700, VER-183, VER-186; or VER-294 | no error | `p11`, `p39`, `p20`, `p34`, `p31`; `p18`, `p19`, `p33` |
| 3 | `timing_control` | VER-188, VER-187, VER-193 | no error | `p05`, `p12`, `p25` |
| 4 | `simulation_statement` | VER-967, VER-968, VER-966, VER-969, ELAB-939 | no error | `p13`, `p28`, `p14` |
| 5 | `event_list` | ELAB-93, ELAB-91, ELAB-407 | no error | `p07`, `p16`, `p35`, `p37` |
| 6 | `async_reset` | ELAB-302; or the warning TRANS-4 | no error | `p15`, `p26`; `p27` |
| 7 | `multiple_drivers` | ELAB-366 | no error | `p08` |
| 8 | `mixed_assignments` | VER-134 | no error | `p22` |
| 9 | `unbounded_loop` | ELAB-900, ELAB-901 | no error | `p29`, `p21` |
| 10 | `instance_mismatch` | LINK-1, VER-216; or the warnings LINK-5 and UID-341 | no error | `p40`, `p41`; `p03` |

Rules:

- Ignore the follow-on errors LBR-0, UID-109, UID-4, VER-518, VER-40, CMD-036, and UID-22. DC gives
  them after an earlier error, because the design `top` then does not exist. CMD-036 and UID-22 come
  from the constraint and report commands of MV's flow.
- DC gives the error VER-294 ("Syntax error") for a class, a dynamic array, and a DPI import,
  although the code is legal SystemVerilog. Thus `vlog` separates class 1 from class 2: if `vlog` also
  reports an error, the class is 1. If `vlog` accepts the code, the class is 2.
- `vlog` compiles each module alone, so it accepts an unknown port or parameter of an instance. The
  mismatch shows only in DC (or in the `vsim` elaboration).
- Keep a design only if its message IDs belong to one class only.

## Designs

- Make mutants: insert one construct of one class into a base design of synth_yesno. The templates
  of harness/mutate.py:

| Class | Templates |
|---|---|
| `illegal_code` | remove one `;`; rename one use of a signal to an undeclared name |
| `unsupported_construct` | `integer` to `real`; `reg` to `time` |
| `timing_control` | `wait (input);` at the start of a clocked block; `begin`/`end` to `fork`/`join` |
| `simulation_statement` | the value of one `x <= ...` to `$random`; `x <= e` to `force x = e` |
| `event_list` | add the other edge of the clock; add a level event |
| `async_reset` | a reset value from a constant to an input; a statement before the reset `if` |
| `multiple_drivers` | a second always block that drives a register |
| `mixed_assignments` | one of two nonblocking assignments to a variable to blocking |
| `unbounded_loop` | the condition of a `for` loop to `i >= 0`; remove the step of a `for` loop |
| `instance_mismatch` | rename a port connection; an unknown parameter; rename the module of an instance |
- Run DC on each mutant. Keep the mutant only if its class (from the table) is the intended class.
- Add natural failures from DC logs of LLM-written RTL, for example the VER-216 error in the
  Orchestrator logs. Mark them.
- Make 50 questions per class (500 questions).

## Controls

- R, M, U, O, and P from README.md.
- Example for M: `// note: the reset is synchronous` on a design with a class 6 error.
- L (labels only): give the options without the descriptions. This shows if the model uses the
  examples in the descriptions as keywords.
- O (option order) is important here, because the list has 10 options.

## Metrics

- The choice metrics from README.md.
- The confusion matrix of the 10 classes. Pairs of classes with many confusions show where the
  descriptions overlap.
- The accuracy per template within each class.

## Open points

1. Confirm the 10 classes. Two classes join several causes: class 2 (types and constructs) and
   class 6 (all asynchronous reset errors).
