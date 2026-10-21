# Dataset v1

MV set this structure on 2026-10-13. It replaces the earlier plan of 500 questions per test.

## Structure

- One test is one RTL design.
- Each design gets one `vlog -sv` run and one run of MV's flow at 500 MHz: step 2, and step 4 if
  the design synthesizes (job `design`). These runs give the correct answers of all the questions
  about the design.
- The questions go in up to three requests per design. Then no question shows the answer of
  another question. For example, only a design that synthesizes has a power testbench.

| Request | Designs | Questions (Jev type) | Correct answer from |
|---|---|---|---|
| `basic` | every usable design | `compiles` (noul), `synthesizes` (noul) | `vlog -sv`; DC with the rules of synth_yesno.md |
| `reason` | a design that does not synthesize | `reason` (choice, the 10 classes of synth_reason.md) | the DC message IDs |
| `performance` | a design that synthesizes | `slack`, `reach`, `area`, `power` (score, 5 levels each) | `results/summary.csv` of step 2 and step 4 |
| `pair` | two old REvolution candidates of one problem | `smaller_area`, `lower_power`, `higher_reach` (choice A/B) | the same runs |

## The levels

| Question | Level 1 | Level 2 | Level 3 | Level 4 | Level 5 |
|---|---|---|---|---|---|
| `slack` (worst slack at 500 MHz) | negative | 0 to 0.5 ns | 0.5 to 1.0 ns | 1.0 to 1.5 ns | 1.5 ns or more |
| `reach` (reachable frequency) | below 1 GHz | 1 to 2 GHz | 2 to 3 GHz | 3 to 4 GHz | 4 GHz or more |
| `area` (1 GE = NAND2_X1 = 0.196608 um2) | below 100 GE | 100 to 1,000 GE | 1,000 to 10,000 GE | 10,000 to 100,000 GE | 100,000 GE or more |
| `power` (with the power testbench in the state) | below 10 uW | 10 to 100 uW | 100 uW to 1 mW | 1 to 10 mW | 10 mW or more |

- The reachable frequency is 1000 / (clock period - worst slack) MHz of the 500 MHz netlist. This
  is the formula of MV's `summary.sh`. `summary.sh` subtracts the slack in ps from the period in
  ns, so for NanGate 15nm it prints no frequency. The harness converts the slack to ns first.
  Example: `mac_int8`, 2.0 ns - 1.43797 ns = 0.56203 ns, which gives 1,779 MHz.
- Kev numbers the levels of a score answer from 0. The scorer maps them to the levels 1 to 5.

## The designs (plan `dataset_v1`, 159 designs)

| Group | Designs | Purpose |
|---|---|---|
| `metrex` | 40: 8 MetRex designs per Sky130 level 1 to 5 | performance questions over a wide range of sizes |
| `revolution` | 10: the smallest REvolution v0 designs, without lstm, cnn, and cpu_rrw | real medium designs |
| `reference` | 15: 10 RTLLM verified designs, 5 sequential VerilogEval reference designs | human-written designs |
| `revold` | 32: 4 old REvolution candidates in each of 8 problems | pair questions |
| `mutant` | 20: 2 per synth_reason class, each on its own base design | the reason question |
| `trap` | 12: 6 pairs of a DC-accepted edit (`#1` delay, `initial`, `$display`) and a rejected twin | rule-of-thumb errors |
| `natural` | 20: 10 failed old REvolution candidates, 10 RTLLM LLM files | real LLM code, of unknown result before the run |
| `noncompile` | 10: one removed `;` or one undeclared name, each on its own base design | the compile question (basic request only) |

Rules:
- lstm, cnn, and cpu_rrw had no usable REvolution run. The power simulation of lstm wrote a VCD of
  8.85 GB in 5 minutes (2026-10-13), so these three designs are not in the plan.
- The power step has a guard: it stops step 4 if the VCD grows above 2 GB or the step runs longer
  than 15 minutes. The design then keeps all its other answers, and only the power question drops.
  After step 4, the harness deletes a VCD above 200 MB and records its size.
- A mutant or a trap design counts only if its base design synthesizes and its DC class is the
  intended class. It gets no performance request, because it is a near copy of its base design.
- A pair counts only if at least one of its values differs by 10% or more, and both variants have
  the same testbench. Each pair is asked in both orders (A/B and B/A).
- The split: 20% development, 80% test, per base design.

## Size and cost (estimates)

- Tool time: about 3 h with one license. A design that synthesizes needs about 85 s (vlog, step 2,
  step 4), and a design that fails early about 5 s. The 8 level-5 designs (large memories) can
  take longer.
- Questions: about 950 in about 360 requests. The exact numbers come from `build dataset_v1` after
  the run.
- Kev-4B on the CPU of mercury: about 4 h for about 360 requests (from the measured 4 s + 23 ms
  per input token). Jev: minutes, less than 0.05 USD.

## Commands

```bash
cd /users/micas/scuycken/workspace/JEV_RTL
python3.12 -m harness label design --plan dataset_v1      # MV starts this run (about 3 h)
python3.12 -m harness status design
python3.12 -m harness build dataset_v1                    # data/questions/dataset_v1.jsonl, no tool
```
