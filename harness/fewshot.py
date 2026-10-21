"""Dataset v1 with three solved examples in the state of each request (the few-shot Kev run).

    python3.12 -m harness.fewshot

MV asked on 2026-10-16 for a second Kev run with three examples in the context: for compilation, one
design that compiles and two that fail, with the labels; the same for synthesis. A power question gets
three designs with only their exact power results, and the same for area and frequency. This also
applies to the pair questions: they get the examples of their metric, not solved pairs.

The builder reads data/questions/dataset_v1.jsonl, the question file of the Kev runs of 2026-10-15,
and writes data/questions/dataset_v1_fewshot3.jsonl, its data card, and the smoke file
data/pilot/dataset_v1_fewshot3_smoke.jsonl. It starts no tool. It reads the first DC error of each
failed example from the DC log in the run folder of that example.

- Only the test split is written. The examples are development designs. The split is per base
  design, so no test design shares a base design with an example.
- Each request has one question, because each question gets the examples of its own question key
  (EXAMPLE_SET). Kev answers each question in its own branch, and a branch sees only the state, so
  one question per request changes nothing else.
- Each request keeps the state fields of its dataset v1 request, the question text, and the correct
  answer. It gets one new state field before the other fields: `examples`, a text with three solved
  examples.
- The level questions (slack, reach, area, power) get the exact value and the level of each example.
  The pair questions get only the exact value.
- All requests of one question key get the same three examples.
- If the Kev install of mercury exists, the builder counts the exact Kev input tokens
  (probes/kev_token_count.py). Then `over_token_limit` means more than 8,192 tokens, the validated
  context of Kev-0.8B, 4B, and 9B. Without the install, it is the estimate of dataset v1.
"""
import hashlib
import json
import re
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path

from . import build, paths

TEST = "dataset_v1_fewshot3"
SOURCE = paths.QUESTIONS_DIR / "dataset_v1.jsonl"
# The SHA-256 of dataset_v1.jsonl in the manifests of the four Kev runs of 2026-10-15. The few-shot
# file must come from this file, else the two runs do not ask the same test questions.
SOURCE_SHA256 = "96814ea63d89b98af7f87c5f6d8e5fe0f35ec710c30755c9d0723fbec4ddbe2a"
OUT = paths.QUESTIONS_DIR / f"{TEST}.jsonl"
SMOKE_SOURCE = paths.PROJECT_DIR / "data" / "pilot" / "dataset_v1_smoke.jsonl"
SMOKE = paths.PROJECT_DIR / "data" / "pilot" / f"{TEST}_smoke.jsonl"

KEV_ENV = paths.VOLUME_DIR / "kev_env.sh"
KEV_DIR = paths.VOLUME_DIR / "kev"
KEV_CONTEXT = 8192              # the validated context of Kev-0.8B, 4B, and 9B (Kev README)

# The examples, development designs chosen on 2026-10-16 with these rules. No example implements the
# function of a test design (problem_key). For each example set:
#   compile      the two shortest designs that vlog rejects, with different errors, and the base
#                design of the first one (it compiles; the two designs differ in one name)
#   synth        the two shortest designs that DC rejects, of two classes, and the base design of
#                the first one (it synthesizes; the two designs differ in one always block)
#   reason       the three shortest designs that DC rejects, of three classes
#   slack, reach, area, power
#                the shortest design with a value of the metric in each range of its levels: 1 to 2,
#                3, and 4 to 5 (METRIC_RANGES; metric_rule_picks checks the lists). This rule
#                excludes revold_rtllm_Prob030_right_shifter_def99b83c05e: the test design
#                rtllm_chatgpt35_t4_right_shifter implements the same RTLLM problem.
EXAMPLES = {
    "compile": ["metrex_05095", "mut_illegal_code_1_metrex_05095", "revold_rtllm_Prob001_accu_650a52a44963"],
    "synth": ["ve_Prob084_ece241_2013_q12", "mut_multiple_drivers_0_ve_Prob084_ece241_2013_q12",
              "mut_illegal_code_1_metrex_05095"],
    "reason": ["mut_multiple_drivers_0_ve_Prob084_ece241_2013_q12", "mut_illegal_code_1_metrex_05095",
               "mut_event_list_0_ve_Prob096_review2015_fsmseq"],
    "slack": ["rtllm_div_16bit", "metrex_24768", "ve_Prob084_ece241_2013_q12"],
    "reach": ["rtllm_div_16bit", "ve_Prob084_ece241_2013_q12", "metrex_05095"],
    "area": ["ve_Prob084_ece241_2013_q12", "rtllm_div_16bit", "metrex_11803"],
    "power": ["ve_Prob084_ece241_2013_q12", "metrex_19362", "metrex_11803"],
}
METRIC_RANGES = [(1, 2), (3,), (4, 5)]
# The example set of each question key. A pair question gets the examples of its metric.
EXAMPLE_SET = {"compiles": "compile", "synthesizes": "synth", "reason": "reason", "slack": "slack",
               "reach": "reach", "area": "area", "power": "power", "smaller_area": "area",
               "lower_power": "power", "higher_reach": "reach"}

HEADERS = {
    "compile": "Three solved examples: three other designs, each with the result of the simulator compiler in `tool`.",
    "synth": "Three solved examples: three other designs, each with the result of the synthesis tool in `tool`.",
    "reason": "Three solved examples: three other designs that the synthesis tool in `tool` does not synthesize, "
              "each with the reason.",
    "slack": "Three solved examples: three other designs, each with the exact worst slack after synthesis with "
             "the flow in `flow` at the clock in `clock`.",
    "reach": "Three solved examples: three other designs, each with the exact reachable clock frequency, "
             "1 / (clock period - worst slack), after synthesis with the flow in `flow` at the clock in `clock`.",
    "area": "Three solved examples: three other designs, each with the exact total cell area after synthesis "
            "with the flow in `flow` at the clock in `clock`.",
    "power": "Three solved examples: three other designs, each with the exact total power after synthesis with "
             "the flow in `flow` at the clock in `clock`.",
}
TARGET = {False: "The question is about the design in `rtl`, not about these examples.",
          True: "The question is about the designs in `rtl_a` and `rtl_b`, not about these examples."}
LEVEL_CRITERIA = {"slack": build.SLACK_CRITERIA, "reach": build.REACH_CRITERIA, "area": build.AREA_CRITERIA,
                  "power": build.POWER_CRITERIA}
# The stimulus of the generated power testbenches of the examples (the comment in each testbench).
TB_TEXT = "a new random value on each data input in every cycle, 4,000 measured cycles"


def first_dc_error(run_dir):
    """The first error line of the DC log of step 2, without the path of the run folder."""
    log = Path(run_dir) / "results" / "2_synth" / "synth.log"
    for line in log.read_text(errors="replace").splitlines():
        if line.startswith("Error:"):
            return " ".join(line.replace(f"{run_dir}/", "").split())
    raise SystemExit(f"no error line in {log}")


def power_text(watt):
    return f"{watt * 1e6:.4g} uW" if watt < 1e-3 else f"{watt * 1e3:.4g} mW"


def design_text(i, r):
    return f"Example {i}. Top module {r['state']['top']}. RTL:\n{r['state']['rtl'].rstrip()}"


def compile_example(i, r):
    if r["correct_answer"]["compiles"]:
        return f"{design_text(i, r)}\nCorrect answer: yes. vlog reports no error."
    return (f"{design_text(i, r)}\nCorrect answer: no. vlog reports at least one error. The first error: "
            f"{r['evidence']['vlog_error']}")


def synth_example(i, r):
    if r["correct_answer"]["synthesizes"]:
        return (f"{design_text(i, r)}\nCorrect answer: yes. The tool finishes with no error, every module "
                "instance is resolved, and every register maps to a library cell.")
    return (f"{design_text(i, r)}\nCorrect answer: no. The tool stops with an error. The first error: "
            f"{first_dc_error(r['evidence']['run_dir'])}")


def reason_example(i, r):
    return (f"{design_text(i, r)}\nCorrect answer: {r['correct_answer']['reason']}. The first error: "
            f"{first_dc_error(r['evidence']['run_dir'])}")


def metric_example(i, r, metric, with_level):
    """A design with the exact value of one metric only. r is its performance record."""
    ev = r["evidence"]
    value = {"slack": lambda: f"worst slack {ev['slack_ps'] / 1000.0:+.3f} ns",
             "reach": lambda: f"reachable clock frequency {ev['reach_mhz']:,.0f} MHz",
             "area": lambda: f"total cell area {ev['area_um2']:,.2f} um2 = {ev['ge']:,.1f} GE",
             "power": lambda: f"total power {power_text(ev['total_power_w'])}, with a generated power testbench "
                              f"({TB_TEXT})"}[metric]()
    level = f" Level: {LEVEL_CRITERIA[metric][r['correct_answer'][metric] - 1]}" if with_level else ""
    return f"{design_text(i, r)}\nResult: {value}.{level}"


def problem_key(r):
    """The function that a design implements: its top module name. All VerilogEval designs have the top
    RefModule or TopModule, so for them the key is the VerilogEval problem number in the design ID."""
    top = r["state"]["top"]
    m = re.search(r"Prob\d{3}", r["design_id"])
    return f"verilogeval {m.group(0)}" if top in ("RefModule", "TopModule") and m else top


def metric_rule_picks(records, metric):
    """The examples of the metric rule: the shortest development design with a value of the metric in
    each range of METRIC_RANGES, of the designs that implement no function of a test design."""
    test_keys = {problem_key(r) for r in records if r["split"] == "test" and r["request"] != "pair"}
    pool = sorted((r for r in records if r["split"] == "dev" and r["request"] == "performance"
                   and metric in r["correct_answer"] and problem_key(r) not in test_keys),
                  key=lambda r: (len(r["state"]["rtl"]), r["design_id"]))
    return [next(r["design_id"] for r in pool if r["correct_answer"][metric] in levels) for levels in METRIC_RANGES]


def example_texts(records):
    """-> {(example set, pair request): the text of the state field `examples`}. Stops if an example
    breaks a rule above."""
    dev = {(r["request"], r["design_id"]): r for r in records if r["split"] == "dev"}

    def rec(request, design_id):
        if (request, design_id) not in dev:
            raise SystemExit(f"example {design_id}: no {request} record in the development split")
        return dev[(request, design_id)]

    compile_recs = [rec("basic", d) for d in EXAMPLES["compile"]]
    synth_recs = [rec("basic", d) for d in EXAMPLES["synth"]]
    reason_recs = [rec("reason", d) for d in EXAMPLES["reason"]]
    checks = [
        ([r["correct_answer"]["compiles"] for r in compile_recs] == [True, False, False], "compile: 1 yes, 2 no"),
        ([r["correct_answer"]["synthesizes"] for r in synth_recs] == [True, False, False], "synth: 1 yes, 2 no"),
        (len({r["correct_answer"]["reason"] for r in reason_recs}) == 3, "reason: three classes"),
    ] + [(EXAMPLES[m] == metric_rule_picks(records, m), f"{m}: the metric rule") for m in LEVEL_CRITERIA]
    for ok, what in checks:
        if not ok:
            raise SystemExit(f"example rule broken: {what}")
    blocks = {
        "compile": [compile_example(i, r) for i, r in enumerate(compile_recs, 1)],
        "synth": [synth_example(i, r) for i, r in enumerate(synth_recs, 1)],
        "reason": [reason_example(i, r) for i, r in enumerate(reason_recs, 1)],
    }
    texts = {(name, False): b for name, b in blocks.items()}
    pair_metrics = {EXAMPLE_SET[k] for k in build.V1_PAIR_QUESTIONS}
    for metric in LEVEL_CRITERIA:
        recs = [rec("performance", d) for d in EXAMPLES[metric]]
        texts[(metric, False)] = [metric_example(i, r, metric, True) for i, r in enumerate(recs, 1)]
        if metric in pair_metrics:
            texts[(metric, True)] = [metric_example(i, r, metric, False) for i, r in enumerate(recs, 1)]
    # The last newline puts an empty line between the examples and the next state field, as after `rtl`.
    return {(name, pair): f"{HEADERS[name]} {TARGET[pair]}\n\n" + "\n\n".join(b) + "\n"
            for (name, pair), b in texts.items()}


def fewshot_records(records, texts):
    """One request per test question of dataset v1, with the field `examples` before the other state fields."""
    out = []
    for r in records:
        if r["split"] != "test":
            continue
        pair = r["request"] == "pair"
        rest = r["question_id"].split(":", 2)[2]          # the design ID, and for a pair also the order
        for key, q in r["questions"].items():
            if pair:                                      # the order stays last (harness.score reads it there)
                pid, order = rest.rsplit(":", 1)
                qid = f"{TEST}:pair:{pid}:{key}:{order}"
            else:
                qid = f"{TEST}:{r['request']}:{rest}:{key}"
            name = EXAMPLE_SET[key]
            state = {"examples": texts[(name, pair)], **r["state"]}
            rec = dict(r, test=TEST, question_id=qid, state=state, questions={key: q},
                       correct_answer={key: r["correct_answer"][key]}, source_question_id=r["question_id"],
                       examples={"set": name, "designs": EXAMPLES[name]})
            rec["est_tokens"] = build.est_tokens({"state": state, "q": rec["questions"]})
            rec["over_token_limit"] = rec["est_tokens"] > build.TOKEN_LIMIT
            out.append(rec)
    return out


def check(out, records):
    """Stop if the few-shot file does not ask the same test questions as dataset v1, or if an example
    shares a base design or a function with a test design."""
    test = [r for r in records if r["split"] == "test"]
    before = Counter(k for r in test for k in r["questions"])
    after = Counter(k for r in out for k in r["questions"])
    if before != after or any(len(r["questions"]) != 1 for r in out):
        raise SystemExit(f"questions per key differ: dataset v1 {dict(before)}, few-shot {dict(after)}")
    truth_before = {(r["question_id"], k): v for r in test for k, v in r["correct_answer"].items()}
    truth_after = {(r["source_question_id"], k): v for r in out for k, v in r["correct_answer"].items()}
    if truth_before != truth_after:
        raise SystemExit("the correct answers differ from dataset v1")
    example_ids = {d for ids in EXAMPLES.values() for d in ids}
    by_id = {r["design_id"]: r for r in records if r["request"] != "pair"}
    shared = {by_id[d]["base_design_id"] for d in example_ids} & {r["base_design_id"] for r in test}
    if shared:
        raise SystemExit(f"test designs share a base design with an example: {sorted(shared)}")
    shared = {problem_key(by_id[d]) for d in example_ids} & {problem_key(r) for r in test if r["request"] != "pair"}
    if shared:
        raise SystemExit(f"test designs implement the function of an example: {sorted(shared)}")


def kev_token_counts(path):
    """-> {question_id: Kev input tokens} (probes/kev_token_count.py), or None without the Kev install."""
    if not (KEV_DIR / ".venv" / "bin" / "python").exists():
        return None
    script = paths.PROJECT_DIR / "probes" / "kev_token_count.py"
    cmd = f"source {KEV_ENV} && cd {KEV_DIR} && HF_HUB_OFFLINE=1 .venv/bin/python {script} {path}"
    res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, check=True)
    return {qid: v[0] for qid, v in json.loads(res.stdout).items()}


def write(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def datacard(out, texts, counted):
    n_q = Counter(k for r in out for k in r["questions"])
    lines = [f"# Data card: {TEST}", "",
             "Dataset v1 with three solved examples in the state of each request (harness/fewshot.py, MV 2026-10-16).",
             "",
             f"- Source: `data/questions/dataset_v1.jsonl`, SHA-256 {SOURCE_SHA256}, the question file of the four "
             "Kev runs of 2026-10-15.",
             "- Split: test only. The examples are development designs, and the split is per base design. No "
             "example implements the function (top module, or VerilogEval problem) of a test design.",
             f"- Requests: {len(out)}, one question each. Questions per key: {dict(n_q)}.",
             "- The questions and the correct answers are those of the test split of dataset v1. The state of each "
             "request is the state of its dataset v1 request, with one new field before the other fields: "
             "`examples`. A pair question gets the examples of its metric, without the levels.", ""]
    keys = list(n_q)
    if counted:
        lines += ["Kev input tokens, exact (probes/kev_token_count.py):", "",
                  f"| Request | Question | Example set | Requests | Median | Maximum | Above {KEV_CONTEXT:,} |",
                  "|---|---|---|---|---|---|---|"]
        for request in dict.fromkeys(r["request"] for r in out):
            for key in keys:
                toks = sorted(r["kev_tokens"] for r in out if r["request"] == request and key in r["questions"])
                if toks:
                    lines.append(f"| {request} | {key} | {EXAMPLE_SET[key]} | {len(toks)} | "
                                 f"{int(statistics.median(toks)):,} | {toks[-1]:,} | {sum(t > KEV_CONTEXT for t in toks)} |")
    else:
        toks = sorted(r["est_tokens"] for r in out)
        lines.append(f"Estimated tokens (no Kev install): median {toks[len(toks) // 2]}, maximum {toks[-1]}, "
                     f"above {build.TOKEN_LIMIT}: {sum(t > build.TOKEN_LIMIT for t in toks)}.")
    lines += ["", "## The examples", "", "The text of the field `examples`, as the model reads it.", ""]
    for (name, pair), text in texts.items():
        users = [k for k, v in EXAMPLE_SET.items() if v == name and (k in build.V1_PAIR_QUESTIONS) == pair]
        lines += [f"### {name}{' (pair questions)' if pair else ''}", "",
                  f"Questions: {users}. Designs: {EXAMPLES[name]}", "", "```text", text, "```", ""]
    return "\n".join(lines)


def main(argv=None):
    data = SOURCE.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    if sha != SOURCE_SHA256:
        raise SystemExit(f"{SOURCE} has SHA-256 {sha}, not {SOURCE_SHA256} (the file of the Kev runs of 2026-10-15)")
    records = [json.loads(line) for line in data.decode().splitlines() if line.strip()]
    texts = example_texts(records)
    out = fewshot_records(records, texts)
    check(out, records)
    write(OUT, out)
    counts = kev_token_counts(OUT)
    if counts is not None:
        for rec in out:
            rec["kev_tokens"] = counts[rec["question_id"]]
            rec["over_token_limit"] = rec["kev_tokens"] > KEV_CONTEXT
        write(OUT, out)
    smoke_ids = {json.loads(line)["question_id"] for line in open(SMOKE_SOURCE)}
    write(SMOKE, [r for r in out if r["source_question_id"] in smoke_ids])
    card = OUT.with_suffix(".card.md")
    card.write_text(datacard(out, texts, counts is not None))
    over = sum(r["over_token_limit"] for r in out)
    limit = f"{KEV_CONTEXT:,} Kev tokens" if counts is not None else f"{build.TOKEN_LIMIT:,} estimated tokens"
    print(f"{TEST}: {len(out)} requests -> {OUT} ({over} above {limit})")
    print(f"smoke file: {SMOKE} ({sum(1 for _ in open(SMOKE))} requests); data card: {card}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
