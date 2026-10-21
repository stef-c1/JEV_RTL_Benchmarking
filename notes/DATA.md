# Data for the JEV_RTL tests

## Rules

- The RTL comes from real designs: public datasets and the designs of MV's agent runs (REvolution and
  Orchestrator).
- The correct answers come only from the flow (README.md). A value from a dataset or from an earlier
  run (for example a MetRex area or a REvolution power) is never a correct answer. My own judgment is
  never a correct answer.
- If a test needs a design that no dataset has, a script makes it from a real design: a mutant, a
  parameter variant, a power testbench, or a clock period. The script records the base design and the
  change.
- I do not write new designs by hand. The only exception is a small set of architecture pairs for
  pair_compare, if the other sources do not give enough pairs. Each such design gets the mark
  `handwritten`.
- Report the results separately for each source, and for public and unpublished sources.

## Datasets

The public datasets are in `/volume1/users/scuycken/jev_rtl_data` on mercury (local disk, no quota),
downloaded on 2026-10-09. The counts below come from these copies and from the run folders, on
2026-10-09.

| Dataset | Content | Origin | License |
|---|---|---|---|
| VerilogEval, `dataset_spec-to-rtl` (commit c498220) | 156 reference designs (`*_ref.sv`), each with `*_prompt.txt` and `*_test.sv`. 73 are sequential. Median size 245 characters, maximum 1,669. | NVIDIA | MIT |
| RTLLM v2.0 (commit 51ed553) | 50 designs with `verified_*.v` and a testbench. 290 LLM-written files in `_chatgpt35` and `_chatgpt4`: 5 folders (t1 to t5) of 29 files for each model. | HKUST | MIT |
| MetRex, `metrex.json` (137 MB, one JSON record per line) | 25,868 modules. Each record has the RTL and a text of its Yosys synthesis result in SkyWater 130 nm. | RTL-Coder 18,450 (written by a GPT model), VeriGen 7,292 (GitHub and textbooks), ISCAS'89 29, ISCAS'85 10, OpenCores 54, NVDLA 33 (Table 1 of the MetRex paper) | BSD-3-Clause |
| REvolution runs, `/users/micas/scuycken/Claude/RTL_LLM_Loop_REvolution` | See the next section. | MV's REvolution loop | own, unpublished |
| Orchestrator runs | 54 variants of `mac_array_int8`, all passed, 56,019 to 200,160 GE at their own clocks | MV's Orchestrator runs | own, unpublished |

The MetRex authors removed duplicates, testbenches, and gate-level netlists. An LLM agent repaired the
synthesis errors and warnings. Thus all MetRex designs synthesize, and some of their code is LLM
code.

## The REvolution designs

MV asked on 2026-10-09 to use these designs for the area and power comparison.

- **Designs.** `Medium_designs_all/` holds 27 medium designs (for example uart, controller, tv80,
  cordic, fifo, aes). Each folder has the v0 RTL and four testbench templates, one of them the power
  testbench `tb_pt_<design>.sv`.
- **Variants.** Each loop iteration writes one record to `test_data.jsonl` (in `Test_data_test_designs`
  and `RERUN`) or `train_data.jsonl` (in `Train_data_medium_clusters/gpt55_corpus`). The record holds
  the full RTL of the primary file (`code`), the outcome, and the verification result.
- **Verified variants.** A variant counts only if the loop verified it: `gate_verify` true, no
  `flow_error`, and `sec_pass` not false. In the training corpus, the outcomes `accepted` and
  `rejected (no improvement)` come only after the verification passed (`train_data_loop.py`,
  `out.ok`).
- **The reference v0.** The loop verified each variant against the v0 of its own run. The harness
  takes that v0 from the runs. For tv80 it differs from `Medium_designs_all`: the runs used
  `tv80_alu.v` (418 lines), and `Medium_designs_all/tv80/tv80.v0.v` also holds the unused tv80 core.
- **The cutoff.** MV's runs in `RERUN` are still running, so the counts grow. The harness uses only
  the runs that started before 2026-10-09 00:00 and did not change after it. The counts of distinct
  RTL with this cutoff:

| Design | Verified variants | Verification |
|---|---|---|
| controller | 2,584 | random differential check against v0, most also SEC |
| uart | 2,132 | the same |
| tv80 | 1,417 | the same |
| 19 other medium designs | 422 in total (20 to 25 each, arm_cpu2 1) | random differential check against v0 (10,000 vectors) |
| `mx_mac_llm_fixed` | not counted | `accuracy` only. Not used, because the function of the variants differs. |

- **Power testbench.** `tb_pt_<design>.sv` drives each input with `$urandom` from the fixed seed
  `32'hC0DE0042`. It holds the reset for 8 cycles, runs 16 warm-up cycles, and then dumps 4,000
  cycles. During these cycles it asserts the reset at random in about 1 of 32 cycles. The template has
  placeholders (`{CLK_HALF}`, the VCD path). The harness fills them for your flow, and it uses the
  instance name of the template (for example `control_unit0`) as `DUT_INSTANCE`.
- **Earlier results.** The REvolution loop measured with NanGate 45nm at a clock target of 0.1 ns
  (`FREQ_LIST=(10000)` MHz). These values help only to select pairs. The labels come from your flow.
- **The design interface.** The verification testbench of the loop instantiates the same top module
  with the same ports for all variants. Thus all variants of one design fit the same power
  testbench.

## The old REvolution candidates (ASP-DAC 2026 runs)

MV asked on 2026-10-09 to check the old REvolution RTL with the flow. The archive
`REvolution.tar.gz` (2026-05-19) holds the runs of the REvolution ASP-DAC 2026 paper: 4 LLM
configurations (gpt-4.1-mini, deepseek, llama3, llama3_baseline) on 156 VerilogEval Spec-to-RTL
problems and 50 RTLLM problems, with about 200 candidates per problem and configuration.

- **The index.** `harness/revolution_old.py` reads the archive once and writes
  `jev_rtl_data/revolution_aspdac2026_index.jsonl`: 170,131 candidate files, 90,058 PPA reports, and
  138,584 distinct candidates (per problem and RTL text).
- **Passed or failed.** REvolution simulates each candidate with the benchmark testbench first.
  Only a passing candidate goes to synthesis, a gate-level check, and PPA (algorithm.py). For
  Prob031_dff of gpt-4.1-mini, the summary gives 210 candidates and a success rate of 0.9, and the
  folder has exactly 189 `.ppa` files (0.9 x 210). Thus a `.ppa` file means that the candidate
  passed (an inference from the code and this count).
- **The counts of distinct candidates:**

| Benchmark | Problems | Passed | Failed | Area max/min in one problem (NG45, median) | Distinct areas per problem (median) | RTL characters (median) |
|---|---|---|---|---|---|---|
| VerilogEval Spec-to-RTL | 156 | 50,637 | 49,265 | 1.89 | 3 | 590 |
| RTLLM | 50 | 13,085 | 25,597 | 3.77 | 27.5 | 1,122 |

- **Use.** The passed candidates of one problem have the same function (within the limits of the
  benchmark testbench), so they give pairs for pair_compare. They are small, so their pairs fit the
  Kev limit of 8,000 tokens. The failed candidates are natural LLM failures for synth_yesno and
  synth_reason, after a DC run.
- **The top module.** VerilogEval candidates use `TopModule`. For RTLLM, the archive has a map
  (`bench/RTLLM/synthesis_top_module_names.json`, copied to `jev_rtl_data/revolution_rtllm_tops.json`).
- **The sample run.** A small sample (32 passed candidates of 8 problems, and 16 failed candidates)
  runs through the flow. The result is in VERIFICATION.md.

## MetRex per area level (estimate)

The level uses the Sky130 area from the MetRex text, divided by the area of `nand2_1` that the same
text gives. This estimate is only for the selection of candidates. The level of a question comes from
DC in NanGate 15nm.

| Level | Designs | Fit in 7,000 Qwen3.5 tokens | With a register-array memory |
|---|---|---|---|
| 1 (below 100 GE) | 14,240 | 14,232 | 146 (1%) |
| 2 (100 to 1,000 GE) | 7,984 | 7,872 | 440 (6%) |
| 3 (1,000 to 10,000 GE) | 2,553 | 2,379 | 607 (24%) |
| 4 (10,000 to 100,000 GE) | 795 | 696 | 506 (64%) |
| 5 (100,000 GE or more) | 296 | 287 | 284 (96%) |

- The token counts use the Qwen3.5-4B-Base tokenizer of the Kev install. The median is 2.68
  characters per token.
- "Register-array memory" means a declaration such as `reg [15:0] memory [0:2047]`. DC builds it from
  flip-flops, so a short declaration gives a very large area.

## Problems in the data

1. **Memories in the large levels.** In MetRex, 96% of level 5 and 64% of level 4 are register-array
   memories. A model can then answer from one declaration. Limit these designs to 25% of each level,
   and fill levels 4 and 5 with other large designs: REvolution designs, Orchestrator arrays, and
   parameter variants of datapaths.
2. **LLM-written code.** 71% of MetRex comes from RTL-Coder, which a GPT model wrote. The RTLLM files,
   the REvolution variants, and the Orchestrator variants are also LLM code. Report LLM code and human
   code separately.
3. **Training data.** The public designs can be in the training data of the models. The questions and
   the correct answers are new, because they come from your flow. The mutants are new code. The
   REvolution and Orchestrator variants are unpublished.
4. **No natural failures in MetRex.** All MetRex designs synthesize. Natural failures come from the
   290 RTLLM LLM files and from the Orchestrator logs.
5. **Spaces in paths.** RTLLM has folder names with spaces (for example `Frequency divider`), and the
   flow refuses a path with a space. The harness copies each design to a run folder with a plain name.
6. **Small designs.** The VerilogEval designs are small (median 245 characters). Most of them will be
   in level 1.
7. **Few REvolution designs with many variants.** Only controller, uart, and tv80 have thousands of
   variants. Most variants of one design have a similar area, so the pairs must cover a range of
   ratios (see pair_compare.md).
8. **Pair size.** A pair holds two RTL files and the testbench. Only ticket_machine,
   vending_machine, cpu_fsm, and dsp give pairs below 8,000 tokens (the Kev limit, estimate).
   controller, uart, and tv80 give 8,700 to 11,600 tokens, so these pairs are for Jev only. fft_oc,
   jpeg_dct, and pcie do not fit in one Jev request, and the plans exclude them.
9. **Level 5.** After the memory limit, MetRex gives only 44 candidates for area level 5, and 40 of
   them are memories.

## Sources and generated variants per test

| Test | Real designs | Made by script from real designs | Target |
|---|---|---|---|
| synth_yesno | True: VerilogEval, RTLLM verified designs, a MetRex sample, REvolution v0 designs, Orchestrator variants. False: RTLLM LLM files that DC rejects, errors from the Orchestrator logs. | False: the mutants of synth_reason. Trap subset: 50 near-twin pairs. | 250 true, 250 false, 100 trap |
| synth_reason | Natural failures with exactly one class | Mutants: one construct of one class, put into a base design of synth_yesno | 50 per class |
| area_level | MetRex (selected per Sky130 level), VerilogEval, RTLLM, REvolution v0 designs, Orchestrator | Parameter variants of datapath designs for levels 4 and 5 | 100 per level, at most 25% memories per level |
| power_level | The designs of area_level | A power testbench in the style of `tb_pt` for each design that has none | 100 per level |
| timing_yesno | The designs of area_level from 10 GE | 4 periods per design | 125 designs x 4 periods |
| pair_compare | Area and power: REvolution variant pairs (526 designs in the plan). Maximum clock and energy: the Orchestrator family (not yet implemented). | Parameter pairs; hand-written architecture pairs only if necessary | 250 pairs x 2 orders per key |

## Tool time

HARNESS.md gives the launch sequence and the tool time of each label job.

## Open points

1. Confirm the limit of 25% register-array memories per level.
