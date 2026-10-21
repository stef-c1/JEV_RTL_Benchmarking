"""Build the question files from the labels. The builders start no tool.

Each test writes one file data/questions/<test>.jsonl. One record is one request to the model:
the state (named fields), one or more typed questions in the format of the Jev API (noul, choice,
score), and the correct answer of each question with its evidence from the flow.

Rules (notes/README.md and the test notes):
  - only designs with status "ok" in the ppa labels, a worst slack of 0 or more at 500 MHz, and
    (for power) a VCD annotation of 95% or more
  - no design within +/-10% of a level edge (area_level, power_level)
  - at most 25% register-array memories per area level
  - pair_compare: a key only if the two values differ by 10% or more; both orders (A/B, B/A); at
    most 25% of the pairs from one design; each variant in at most 3 pairs
  - a fixed seed, so the same labels give the same questions
  - the split: 20% development, 80% test, per base design
"""
import hashlib
import itertools
import json
import math
import random
import re
from collections import Counter, defaultdict

from . import labels, paths

SEED = 20261009
CHARS_PER_TOKEN = 2.68          # median of MetRex with the Qwen3.5 tokenizer (notes/DATA.md)
TOKEN_LIMIT = 8000              # the validated context of Kev-0.8B, 4B, and 9B is 8,192 tokens
JEV_LIMIT = 30000               # below the Jev limit of 32k tokens for the state plus the longest question

FLOW_TEXT = ("Synopsys Design Compiler (compile_ultra), NanGate 15nm Open Cell Library, typical "
             "corner 0.8 V and 25 C, input and output delay 10% of the clock period, clock "
             "uncertainty 50 ps.")
CLOCK_TEXT = "500 MHz (clock period 2.0 ns)"

AREA_EDGES_GE = [100, 1000, 10000, 100000]
AREA_CRITERIA = ["Below 100 GE.", "100 GE to 1,000 GE.", "1,000 GE to 10,000 GE.",
                 "10,000 GE to 100,000 GE.", "100,000 GE or more."]
POWER_EDGES_UW = [10, 100, 1000, 10000]
POWER_CRITERIA = ["Below 10 uW.", "10 uW to 100 uW.", "100 uW to 1 mW.", "1 mW to 10 mW.",
                  "10 mW or more."]

MEM_RE = re.compile(r"\breg\b[^;]*\]\s*\w+\s*\[[^\]]+\]")


def rtl_text(files):
    """All source files in one text, each after a line with its file name."""
    return "".join(f"// ---- file: {name} ----\n{text.rstrip()}\n" for name, text in files)


def est_tokens(obj):
    return math.ceil(len(json.dumps(obj)) / CHARS_PER_TOKEN)


def level_of(value, edges):
    """Return (level 1..5, distance to the nearest edge as a fraction of the edge)."""
    level = 1 + sum(1 for e in edges if value >= e)
    dist = min(abs(value - e) / e for e in edges)
    return level, dist


def split_of(base_id):
    """20% development, 80% test, from a hash of the base design (the same base, the same split)."""
    h = int(hashlib.sha256(f"{SEED}:{base_id}".encode()).hexdigest(), 16)
    return "dev" if h % 5 == 0 else "test"


def load_ppa():
    path = labels.label_file("ppa")
    if not path.exists():
        return []
    return [json.loads(l) for l in open(path)]


def _ok_ppa(r, need_power):
    if r.get("status") != "ok" or r.get("area_um2") is None or r.get("slack_ps") is None:
        return False
    if r["slack_ps"] < 0:
        return False
    if need_power:
        ann = (r.get("annotation") or {}).get("annotated_pct")
        if r.get("total_power_w") is None or ann is None or ann < 95.0:
            return False
    return True


def _base_id(r):
    m = r.get("meta") or {}
    if r.get("source") == "revolution":
        return f"rev_{m.get('key')}"
    return r["design_id"]


def write_questions(test, records):
    """Write the records of one test. A record above JEV_LIMIT tokens (estimate) does not fit in
    one Jev request, so it is not written."""
    records = [r for r in records if r.get("est_tokens", 0) <= JEV_LIMIT]
    paths.QUESTIONS_DIR.mkdir(parents=True, exist_ok=True)
    out = paths.QUESTIONS_DIR / f"{test}.jsonl"
    with open(out, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    return out


def _level_questions(test, per_level, value_key, edges, criteria, instruction, with_tb):
    rng = random.Random(SEED)
    rows = [r for r in load_ppa() if _ok_ppa(r, need_power=with_tb)]
    # area_level and power_level use each base design once: the variants of the new REvolution
    # runs go to pair_compare only. (Without this rule, the 20 router variants of the pilot filled
    # power level 3 with near-identical designs. Found in the preview build of 2026-10-13.)
    rows = [r for r in rows if r.get("source") != "revolution" or r["meta"].get("variant") == "v0"]
    # The old REvolution candidates (up to 6 per problem, same function) are only for pair_compare.
    rows = [r for r in rows if r.get("source") != "revolution_old"]
    by_level = defaultdict(list)
    dropped = Counter()
    for r in rows:
        value = r["area_um2"] / paths.GE_UM2 if value_key == "ge" else r["total_power_w"] * 1e6
        if value <= 0:
            dropped["zero"] += 1
            continue
        level, dist = level_of(value, edges)
        if dist < 0.10:
            dropped["near_edge"] += 1
            continue
        r["_value"], r["_level"] = value, level
        by_level[level].append(r)
    picked = []
    for level in range(1, 6):
        pool = sorted(by_level[level], key=lambda r: r["design_id"])
        rng.shuffle(pool)
        if test == "area_level":
            mem = [r for r in pool if MEM_RE.search(rtl_text(r["files"]))]
            non = [r for r in pool if not MEM_RE.search(rtl_text(r["files"]))]
            n_mem = min(len(mem), per_level // 4)
            pool = non[:per_level - n_mem] + mem[:n_mem]
        picked.extend(pool[:per_level])
    records = []
    for r in picked:
        state = {"rtl": rtl_text(r["files"]), "top": r["top"], "flow": FLOW_TEXT, "clock": CLOCK_TEXT}
        if with_tb:
            state["tb_power"] = r["tb_power"]
        question = {"type": "score", "instructions": instruction, "criteria": criteria}
        rec = {
            "test": test, "question_id": f"{test}:{r['design_id']}", "design_id": r["design_id"],
            "base_design_id": _base_id(r), "source": r["source"], "variant": "original",
            "split": split_of(_base_id(r)), "state": state, "questions": {"level": question},
            "correct_answer": {"level": r["_level"]},
            "evidence": {"flow": "flow/RTL_flow_Nangate15 (zip of 2026-08-18)",
                         "run_dir": r.get("run_dir"), "area_um2": r["area_um2"],
                         "ge": r["area_um2"] / paths.GE_UM2, "slack_ps": r["slack_ps"],
                         "total_power_w": r.get("total_power_w"), "annotation": r.get("annotation"),
                         "tb_how": r.get("tb_how"), "value": r["_value"]},
        }
        rec["est_tokens"] = est_tokens({"state": state, "q": question})
        rec["over_token_limit"] = rec["est_tokens"] > TOKEN_LIMIT
        records.append(rec)
    counts = Counter(r["correct_answer"]["level"] for r in records)
    return records, {"per_level": dict(sorted(counts.items())), "dropped": dict(dropped),
                     "candidates_per_level": {L: len(v) for L, v in sorted(by_level.items())}}


def build_area_level(per_level=100):
    return _level_questions(
        "area_level", per_level, "ge", AREA_EDGES_GE, AREA_CRITERIA,
        "Estimate the total cell area of the module `top` in `rtl` after synthesis with the flow in "
        "`flow` at the clock in `clock`. 1 GE is the area of one two-input NAND gate. Select the "
        "area level.", with_tb=False)


def build_power_level(per_level=100):
    return _level_questions(
        "power_level", per_level, "uw", POWER_EDGES_UW, POWER_CRITERIA,
        "Estimate the total power (dynamic plus leakage) of the module `top` in `rtl` after "
        "synthesis with the flow in `flow` at the clock in `clock`, with the stimulus of the power "
        "testbench in `tb_power`. Select the power level.", with_tb=True)


PAIR_QUESTIONS = {
    "smaller_area": ("Which variant has the smaller total cell area after synthesis with the flow in "
                     "`flow` at the clock in `clock`?", "area_um2"),
    "lower_power": ("Which variant has the lower total power after synthesis with the flow in `flow` "
                    "at the clock in `clock`, with the stimulus of the power testbench in "
                    "`tb_power`?", "total_power_w"),
}
PAIR_OPTIONS = {"A": "the design in `rtl_a`", "B": "the design in `rtl_b`"}
RATIO_BINS = [(1.1, 1.25), (1.25, 2.0), (2.0, float("inf"))]


def build_pair_compare(pairs_per_key=250, max_design_share=0.25, max_pairs_per_variant=3):
    """REvolution pairs for smaller_area and lower_power (notes/pair_compare.md): the variants of
    the new REvolution runs (one group per design) and the passed candidates of the old REvolution
    runs (one group per problem)."""
    rng = random.Random(SEED)
    rows = [r for r in load_ppa() if r.get("source") in ("revolution", "revolution_old")
            and _ok_ppa(r, need_power=True)]
    by_design = defaultdict(list)
    for r in rows:
        # One group per design of the new REvolution runs, and one group per problem of the old
        # REvolution runs (all passed candidates of one problem have the same function).
        group = r["meta"]["key"] if r["source"] == "revolution" else f"old_{r['meta']['problem']}"
        by_design[group].append(r)
    cap = max(1, int(pairs_per_key * max_design_share))
    candidates = []
    for key, group in sorted(by_design.items()):
        group.sort(key=lambda r: r["design_id"])
        for a, b in itertools.combinations(group, 2):
            if a["tb_power"] != b["tb_power"]:
                continue        # both variants must run the same testbench
            ratios = {}
            for qkey, (_text, field) in PAIR_QUESTIONS.items():
                hi, lo = max(a[field], b[field]), min(a[field], b[field])
                if lo > 0 and hi / lo >= 1.1:
                    ratios[qkey] = hi / lo
            if ratios:
                candidates.append((key, a, b, ratios))
    rng.shuffle(candidates)
    chosen = select_pairs(candidates, pairs_per_key, cap, max_pairs_per_variant)
    records = []
    for key, a, b, ratios in chosen:
        for order in ("AB", "BA"):
            x, y = (a, b) if order == "AB" else (b, a)
            state = {"rtl_a": rtl_text(x["files"]), "rtl_b": rtl_text(y["files"]), "top": x["top"],
                     "flow": FLOW_TEXT, "clock": CLOCK_TEXT, "tb_power": x["tb_power"]}
            questions, answers, evidence = {}, {}, {}
            for qkey in ratios:
                text, field = PAIR_QUESTIONS[qkey]
                questions[qkey] = {"type": "choice", "instructions": text, "criteria": PAIR_OPTIONS}
                answers[qkey] = "A" if x[field] < y[field] else "B"
                evidence[qkey] = {"field": field, "a": x[field], "b": y[field], "ratio": ratios[qkey]}
            pair_id = "~".join(sorted([a["design_id"], b["design_id"]]))
            rec = {"test": "pair_compare", "question_id": f"pair_compare:{pair_id}:{order}",
                   "design_id": pair_id, "base_design_id": f"rev_{key}", "source": x["source"],
                   "variant": f"order_{order}", "split": split_of(f"rev_{key}"), "state": state,
                   "questions": questions, "correct_answer": answers,
                   "evidence": dict(evidence, run_dir_a=x.get("run_dir"), run_dir_b=y.get("run_dir"),
                                    flow="flow/RTL_flow_Nangate15 (zip of 2026-08-18)")}
            rec["est_tokens"] = est_tokens({"state": state, "q": questions})
            rec["over_token_limit"] = rec["est_tokens"] > TOKEN_LIMIT
            records.append(rec)
    per_key = Counter(k for c in chosen for k in c[3])
    per_design = Counter(c[0] for c in chosen)
    stats = {"pairs": len(chosen), "per_key": dict(per_key), "per_design": dict(per_design),
             "candidate_pairs": len(candidates),
             "ratio_bins": dict(Counter(next(f"{lo}-{hi}" for lo, hi in RATIO_BINS
                                             if lo <= max(c[3].values()) < hi) for c in chosen))}
    return records, stats


def _bin(ratio):
    for i, (low, high) in enumerate(RATIO_BINS):
        if low <= ratio < high:
            return i
    return None


def select_pairs(candidates, pairs_per_key, design_cap, max_pairs_per_variant):
    """Select pairs round-robin over the ratio bins.

    candidates  a shuffled list of (design key, record a, record b, {question key: ratio})
    Each round takes the next acceptable pair from each bin. A pair is acceptable if its design has
    fewer than design_cap pairs, both variants are in fewer than max_pairs_per_variant pairs, and
    at least one of its question keys has fewer than pairs_per_key pairs. The selection stops when
    a full round adds no pair. The bin of a pair is the bin of its largest ratio.
    """
    bins = [[] for _ in RATIO_BINS]
    for c in candidates:
        i = _bin(max(c[3].values()))
        if i is not None:
            bins[i].append(c)
    pointer = [0] * len(bins)
    use, per_design, per_key = Counter(), Counter(), Counter()
    chosen = []

    def acceptable(c):
        key, a, b, ratios = c
        return (per_design[key] < design_cap
                and use[a["design_id"]] < max_pairs_per_variant
                and use[b["design_id"]] < max_pairs_per_variant
                and any(per_key[k] < pairs_per_key for k in ratios))

    while True:
        added = False
        for i, pool in enumerate(bins):
            while pointer[i] < len(pool):
                c = pool[pointer[i]]
                pointer[i] += 1
                if acceptable(c):
                    chosen.append(c)
                    per_design[c[0]] += 1
                    use[c[1]["design_id"]] += 1
                    use[c[2]["design_id"]] += 1
                    for k in c[3]:
                        per_key[k] += 1
                    added = True
                    break
        if not added:
            return chosen


# ---------------------------------------------------------------- synth_yesno and synth_reason

TOOL_TEXT = ("Synopsys Design Compiler U-2022.12-SP2 (analyze -format sverilog, elaborate, link, "
             "compile_ultra), NanGate 15nm Open Cell Library.")
REASON_OPTIONS = {
    "illegal_code": "The code is not legal Verilog or SystemVerilog: a syntax error, an undeclared name, "
                    "a non-constant range, or a procedural assignment to a net.",
    "unsupported_construct": "The code is legal for a simulator, but it uses a data type or construct that "
                             "synthesis does not support: real, time, string, trireg, a class, a dynamic "
                             "array, a DPI import, or a user-defined primitive.",
    "timing_control": "The code uses a timing control that synthesis does not support: wait, fork-join, "
                      "or an event trigger (->).",
    "simulation_statement": "The code uses a statement or system function for simulation only: "
                            "force-release, procedural assign-deassign, or $random.",
    "event_list": "An event list that synthesis does not support: both edges of one signal, edge and level "
                  "events mixed, or different edges in one process.",
    "async_reset": "An asynchronous reset or set that synthesis cannot build: statements outside the reset "
                   "if-else, a second edge signal without the reset template, or a reset to a non-constant "
                   "value.",
    "multiple_drivers": "A signal has more than one driver, for example assignments in two always blocks.",
    "mixed_assignments": "One variable gets blocking and nonblocking assignments in the same always block.",
    "unbounded_loop": "A loop or a recursion that synthesis cannot unroll: a forever loop with no timing "
                      "control, or a recursion with no constant limit.",
    "instance_mismatch": "A module instance does not match a module: a missing module, an unknown parameter, "
                         "or an unknown port.",
}
YESNO_CRITERIA = {
    "true": "The tool finishes with no error, every module instance is resolved, and every register maps "
            "to a library cell.",
    "false": "The tool stops with an error, or a module instance is not resolved, or a register cannot map "
             "to a library cell.",
}
# DC ignores these constructs with a warning. The textbook answer and the tool answer differ, so
# these designs go only into the trap subset (notes/synth_yesno.md).
IGNORED_WARNINGS = {"VER-281", "VER-176", "VER-130", "VER-173", "VER-274", "ELAB-310"}
SYSTEM_TASK_RE = re.compile(r"\$(display|write|monitor|strobe|fopen|fwrite|fclose|finish|stop)\b")


# Sources of natural LLM failures: the RTLLM files of GPT-3.5 and GPT-4, and the old REvolution
# candidates that failed in REvolution.
NATURAL_SOURCES = ("rtllm_llm", "revolution_old")


def load_synth():
    path = labels.label_file("synth")
    return [json.loads(l) for l in open(path)] if path.exists() else []


def _synth_state(r):
    return {"rtl": rtl_text(r["files"]), "top": r["top"], "tool": TOOL_TEXT}


def _synth_evidence(r):
    s = r["synth"]
    return {"flow": "flow/RTL_flow_Nangate15 (zip of 2026-08-18), step 2", "run_dir": r.get("run_dir"),
            "dc_errors": s["errors"], "dc_warnings": s["warnings"], "classes": s["classes"],
            "vlog_ok": r.get("vlog_ok"), "edit": (r.get("meta") or {}).get("edit"),
            "template": (r.get("meta") or {}).get("template"),
            "base_design_id": (r.get("meta") or {}).get("base_design_id")}


def _base_of(r):
    """The base design of a record: the base of a mutant or trap, the problem of an old REvolution
    candidate (all candidates of one problem are in the same split), else the design itself."""
    m = r.get("meta") or {}
    if m.get("base_design_id"):
        return m["base_design_id"]
    if r.get("source") == "revolution_old" and m.get("problem"):
        return f"revold_{m['problem']}"
    return r["design_id"]


def _reason_pool(rows):
    """Mutants whose DC class is the intended class, and natural failures with one class."""
    pool = defaultdict(list)
    for r in rows:
        reason = r["synth"]["reason"]
        if not reason:
            continue
        if r["design_id"].startswith("mut_") and reason == r["meta"].get("intended"):
            pool[reason].append(r)
        elif r.get("source") in NATURAL_SOURCES:
            pool[reason].append(r)
    for cls in pool:
        # natural LLM failures first, then the mutants
        pool[cls].sort(key=lambda r: (r.get("source") not in NATURAL_SOURCES, r["design_id"]))
    return pool


def build_synth_reason(per_class=50):
    rows = load_synth()
    pool = _reason_pool(rows)
    question = {"type": "choice", "instructions": "The tool in `tool` does not synthesize the module `top` "
                "in `rtl` to a complete gate-level netlist. Select the reason.", "criteria": REASON_OPTIONS}
    records = []
    for cls in REASON_OPTIONS:
        for r in pool.get(cls, [])[:per_class]:
            state = _synth_state(r)
            rec = {"test": "synth_reason", "question_id": f"synth_reason:{r['design_id']}",
                   "design_id": r["design_id"], "base_design_id": _base_of(r), "source": r["source"],
                   "variant": "natural" if r.get("source") in NATURAL_SOURCES else "mutant",
                   "split": split_of(_base_of(r)), "state": state, "questions": {"reason": question},
                   "correct_answer": {"reason": cls}, "evidence": _synth_evidence(r)}
            rec["est_tokens"] = est_tokens({"state": state, "q": question})
            rec["over_token_limit"] = rec["est_tokens"] > TOKEN_LIMIT
            records.append(rec)
    return records, {"per_class": dict(Counter(r["correct_answer"]["reason"] for r in records)),
                     "available_per_class": {c: len(v) for c, v in pool.items()}}


def build_synth_yesno(per_side=250):
    rows = load_synth()
    by_id = {r["design_id"]: r for r in rows}
    pool = _reason_pool(rows)
    per_class = per_side // len(REASON_OPTIONS)
    false_rows = []
    for cls in REASON_OPTIONS:
        false_rows.extend(pool.get(cls, [])[:per_class])
    clean = [r for r in rows if r["synth"]["synthesizes"] and not r["design_id"].startswith(("mut_", "trap_", "probe_"))
             and not (set(r["synth"]["warnings"]) & IGNORED_WARNINGS)
             and not SYSTEM_TASK_RE.search(rtl_text(r["files"]))]
    twins = [by_id[b] for b in dict.fromkeys(_base_of(r) for r in false_rows) if b in by_id and by_id[b] in clean]
    rest = sorted((r for r in clean if r not in twins), key=lambda r: r["design_id"])
    random.Random(SEED).shuffle(rest)
    true_rows = (twins + rest)[:per_side]
    question = {"type": "noul", "instructions": "Does the tool in `tool` synthesize the module `top` in `rtl` "
                "to a complete gate-level netlist?", "criteria": YESNO_CRITERIA}
    records = []

    def add(r, answer, variant):
        state = _synth_state(r)
        rec = {"test": "synth_yesno", "question_id": f"synth_yesno:{r['design_id']}", "design_id": r["design_id"],
               "base_design_id": _base_of(r), "source": r["source"], "variant": variant,
               "split": split_of(_base_of(r)), "state": state, "questions": {"synthesizes": question},
               "correct_answer": {"synthesizes": answer}, "evidence": _synth_evidence(r)}
        rec["est_tokens"] = est_tokens({"state": state, "q": question})
        rec["over_token_limit"] = rec["est_tokens"] > TOKEN_LIMIT
        records.append(rec)

    for r in false_rows:
        add(r, False, "natural" if r.get("source") in NATURAL_SOURCES else "mutant")
    for r in true_rows:
        add(r, True, "original")
    # Trap pairs: the trap side must synthesize, and the twin side must show its intended class.
    pairs = defaultdict(dict)
    for r in rows:
        m = r.get("meta") or {}
        if r["design_id"].startswith("trap_"):
            pairs[(m["trap_kind"], m["pair"])][m["side"]] = r
    n_traps = 0
    for key in sorted(pairs):
        sides = pairs[key]
        t, w = sides.get("trap"), sides.get("twin")
        if t and w and t["synth"]["synthesizes"] and w["synth"]["reason"] == w["meta"]["intended"]:
            add(t, True, f"trap_{key[0]}")
            add(w, False, f"trap_twin_{key[0]}")
            n_traps += 1
    return records, {"false": len(false_rows), "true": len(true_rows), "trap_pairs": n_traps,
                     "false_per_class": dict(Counter(r["synth"]["reason"] for r in false_rows))}


# ---------------------------------------------------------------- timing_yesno

def build_timing_yesno():
    path = labels.label_file("period")
    rows = [json.loads(l) for l in open(path)] if path.exists() else []
    records = []
    question_text = ("The module `top` in `rtl` is synthesized with the flow in `flow` for the clock period "
                     "in `clock`. Does the synthesized design meet this clock period?")
    criteria = {"true": "The worst slack is zero or positive. Every timed path fits in the clock period.",
                "false": "The worst slack is negative. At least one path is longer than the clock period."}
    for r in rows:
        if r.get("status") != "ok":
            continue
        for run in r.get("periods", []):
            if run["slack_ps"] is None:
                continue
            state = {"rtl": rtl_text(r["files"]), "top": r["top"], "flow": FLOW_TEXT,
                     "clock": f"clock period {run['period_ns']:.3f} ns"}
            question = {"type": "noul", "instructions": question_text, "criteria": criteria}
            rec = {"test": "timing_yesno", "question_id": f"timing_yesno:{r['design_id']}:{run['factor']}",
                   "design_id": r["design_id"], "base_design_id": r["design_id"], "source": r["source"],
                   "variant": f"factor_{run['factor']}", "split": split_of(r["design_id"]), "state": state,
                   "questions": {"meets": question}, "correct_answer": {"meets": run["slack_ps"] >= 0},
                   "evidence": {"flow": "flow/RTL_flow_Nangate15 (zip of 2026-08-18), step 2",
                                "slack_ps": run["slack_ps"], "period_ns": run["period_ns"],
                                "tmin_ns": r["tmin"]["tmin_ns"], "factor": run["factor"],
                                "results_dir": run["results_dir"]}}
            rec["est_tokens"] = est_tokens({"state": state, "q": question})
            rec["over_token_limit"] = rec["est_tokens"] > TOKEN_LIMIT
            records.append(rec)
    return records, {"questions": len(records),
                     "meets": dict(Counter(r["correct_answer"]["meets"] for r in records)),
                     "per_factor": dict(Counter((r["variant"], r["correct_answer"]["meets"]) for r in records))}


# ---------------------------------------------------------------- dataset v1 (design-centric)

V1_TOOL_TEXT = ("Compilation: Siemens QuestaSim 2022.4, vlog -sv. Synthesis: Synopsys Design Compiler "
                "U-2022.12-SP2 (analyze -format sverilog, elaborate, link, compile_ultra), NanGate 15nm "
                "Open Cell Library.")
SLACK_EDGES_NS = [0.0, 0.5, 1.0, 1.5]
SLACK_CRITERIA = ["Negative: the design misses the clock period.", "0 ns to 0.5 ns.", "0.5 ns to 1.0 ns.",
                  "1.0 ns to 1.5 ns.", "1.5 ns or more."]
REACH_EDGES_MHZ = [1000, 2000, 3000, 4000]
REACH_CRITERIA = ["Below 1 GHz.", "1 GHz to 2 GHz.", "2 GHz to 3 GHz.", "3 GHz to 4 GHz.", "4 GHz or more."]
V1_QUESTIONS = {
    "compiles": {"type": "noul", "instructions": "Does the simulator compiler in `tool` compile the RTL in `rtl` "
                 "with no error?", "criteria": {"true": "vlog reports no error.", "false": "vlog reports at least one error."}},
    "synthesizes": {"type": "noul", "instructions": "Does the synthesis tool in `tool` synthesize the module `top` "
                    "in `rtl` to a complete gate-level netlist?", "criteria": YESNO_CRITERIA},
    "reason": {"type": "choice", "instructions": "The synthesis tool in `tool` does not synthesize the module `top` "
               "in `rtl` to a complete gate-level netlist. Select the reason.", "criteria": REASON_OPTIONS},
    "slack": {"type": "score", "instructions": "The flow in `flow` synthesizes the module `top` in `rtl` for the clock "
              "in `clock`. What is the worst slack of the synthesized netlist? Select the level.",
              "criteria": SLACK_CRITERIA},
    "reach": {"type": "score", "instructions": "The flow in `flow` synthesizes the module `top` in `rtl` for the clock "
              "in `clock`. The reachable clock frequency is 1 / (clock period - worst slack) of that netlist. "
              "Select its level.", "criteria": REACH_CRITERIA},
    "area": {"type": "score", "instructions": "Estimate the total cell area of the module `top` in `rtl` after "
             "synthesis with the flow in `flow` at the clock in `clock`. 1 GE is the area of one two-input NAND "
             "gate. Select the area level.", "criteria": AREA_CRITERIA},
    "power": {"type": "score", "instructions": "Estimate the total power (dynamic plus leakage) of the module `top` in "
              "`rtl` after synthesis with the flow in `flow` at the clock in `clock`, with the stimulus of the power "
              "testbench in `tb_power`. Select the power level.", "criteria": POWER_CRITERIA},
}
V1_PAIR_QUESTIONS = {
    "smaller_area": ("Which variant has the smaller total cell area after synthesis with the flow in `flow` at "
                     "the clock in `clock`?", "area_um2"),
    "lower_power": ("Which variant has the lower total power after synthesis with the flow in `flow` at the clock "
                    "in `clock`, with the stimulus of the power testbench in `tb_power`?", "total_power_w"),
    "higher_reach": ("Which variant has the higher reachable clock frequency, 1 / (clock period - worst slack), "
                     "after synthesis with the flow in `flow` at the clock in `clock`?", "reach_mhz"),
}


def slack_level(slack_ns):
    """1 for a negative slack, else 2 + the number of the edges 0.5, 1.0, 1.5 ns at or below it."""
    if slack_ns < 0:
        return 1
    return 2 + sum(1 for e in SLACK_EDGES_NS[1:] if slack_ns >= e)


def load_design():
    path = labels.label_file("design")
    return [json.loads(l) for l in open(path)] if path.exists() else []


def _v1_record(r, kind, state, qkeys, answers, evidence):
    questions = {k: V1_QUESTIONS[k] for k in qkeys}
    rec = {"test": "dataset_v1", "request": kind, "question_id": f"dataset_v1:{kind}:{r['design_id']}",
           "design_id": r["design_id"], "base_design_id": _base_of(r), "source": r["source"],
           "group": (r.get("meta") or {}).get("group"), "split": split_of(_base_of(r)),
           "state": state, "questions": questions, "correct_answer": answers, "evidence": evidence}
    rec["est_tokens"] = est_tokens({"state": state, "q": questions})
    rec["over_token_limit"] = rec["est_tokens"] > TOKEN_LIMIT
    return rec


def build_dataset_v1():
    """One file with the requests of dataset v1 (notes/DATASET.md).

    Per design, up to three requests, so that no question shows the answer of another question:
      basic        compiles, synthesizes                     (every usable design)
      reason       the synth_reason class                    (a design that does not synthesize)
      performance  slack, reach, area, and power             (a design that synthesizes)
    and for the old REvolution candidates, pair requests (A/B, both orders) per problem.
    A mutant or a trap design counts only if its base design synthesizes and its DC class is the
    intended class. A mutant or a trap design gets no performance request (it is a near copy of
    its base).
    """
    rows = [r for r in load_design() if r.get("status") != "harness_error" and r.get("synth")]
    by_id = {r["design_id"]: r for r in rows}
    records, skipped = [], Counter()
    for r in rows:
        m = r.get("meta") or {}
        group = m.get("group")
        syn = r["synth"]
        if group in ("mutant", "trap", "noncompile"):
            base = by_id.get(m.get("base_design_id"))
            if not base or not base["synth"]["synthesizes"]:
                skipped["base does not synthesize"] += 1
                continue
            if m.get("intended") and syn["reason"] != m["intended"]:
                skipped[f"{group}: DC class is not the intended class"] += 1
                continue
            if group == "trap" and m.get("side") == "trap" and not syn["synthesizes"]:
                skipped["trap side does not synthesize"] += 1
                continue
        files_state = {"rtl": rtl_text(r["files"]), "top": r["top"], "tool": V1_TOOL_TEXT}
        ev = {"run_dir": r.get("run_dir"), "vlog_ok": r.get("vlog_ok"), "vlog_error": r.get("vlog_error"),
              "dc_errors": syn["errors"], "dc_warnings": syn["warnings"], "classes": syn["classes"],
              "edit": m.get("edit"), "flow": "flow/RTL_flow_Nangate15 (zip of 2026-08-18), 500 MHz"}
        records.append(_v1_record(r, "basic", files_state, ["compiles", "synthesizes"],
                                  {"compiles": bool(r.get("vlog_ok")), "synthesizes": syn["synthesizes"]}, ev))
        if not syn["synthesizes"]:
            if group == "noncompile":
                continue          # basic request only (DATASET.md)
            if syn["reason"]:
                records.append(_v1_record(r, "reason", files_state, ["reason"], {"reason": syn["reason"]}, ev))
            else:
                skipped["no single DC class"] += 1
            continue
        if group in ("mutant", "trap", "noncompile"):
            continue
        if r.get("slack_ps") is None or r.get("area_um2") is None or r["area_um2"] <= 0:
            skipped["no slack or area"] += 1
            continue
        state = {"rtl": rtl_text(r["files"]), "top": r["top"], "flow": FLOW_TEXT, "clock": CLOCK_TEXT}
        keys = ["slack", "reach", "area"]
        ge = r["area_um2"] / paths.GE_UM2
        answers = {"slack": slack_level(r["slack_ps"] / 1000.0), "area": level_of(ge, AREA_EDGES_GE)[0]}
        answers["reach"] = level_of(r["reach_mhz"], REACH_EDGES_MHZ)[0] if r.get("reach_mhz") else None
        if answers["reach"] is None:
            keys.remove("reach")
            answers.pop("reach")
        ann = (r.get("annotation") or {}).get("annotated_pct")
        if r.get("status") == "ok" and r.get("total_power_w") and ann is not None and ann >= 95:
            state["tb_power"] = r["tb_power"]
            keys.append("power")
            answers["power"] = level_of(r["total_power_w"] * 1e6, POWER_EDGES_UW)[0]
        else:
            skipped[f"no power ({r.get('status')})"] += 1
        pev = dict(ev, area_um2=r["area_um2"], ge=ge, slack_ps=r["slack_ps"], period_ns=r.get("period_ns"),
                   reach_mhz=r.get("reach_mhz"), total_power_w=r.get("total_power_w"), annotation=r.get("annotation"),
                   tb_how=r.get("tb_how"), clock_port=r.get("clock_port"))
        records.append(_v1_record(r, "performance", state, keys, answers, pev))
    # Pair requests: the old REvolution candidates of one problem, with the same testbench.
    groups = defaultdict(list)
    for r in rows:
        if (r.get("meta") or {}).get("group") == "revold" and r.get("status") == "ok" and r.get("slack_ps") is not None \
                and ((r.get("annotation") or {}).get("annotated_pct") or 0) >= 95:
            groups[r["meta"]["problem"]].append(r)
    n_pairs = 0
    for problem, g in sorted(groups.items()):
        g.sort(key=lambda r: r["design_id"])
        for a, b in itertools.combinations(g, 2):
            if a["tb_power"] != b["tb_power"]:
                skipped["pair: different testbench"] += 1
                continue
            keys = {}
            for qkey, (_text, field) in V1_PAIR_QUESTIONS.items():
                hi, lo = max(a[field] or 0, b[field] or 0), min(a[field] or 0, b[field] or 0)
                if lo > 0 and hi / lo >= 1.1:
                    keys[qkey] = hi / lo
            if not keys:
                skipped["pair: no value differs by 10%"] += 1
                continue
            n_pairs += 1
            for order in ("AB", "BA"):
                x, y = (a, b) if order == "AB" else (b, a)
                state = {"rtl_a": rtl_text(x["files"]), "rtl_b": rtl_text(y["files"]), "top": x["top"],
                         "flow": FLOW_TEXT, "clock": CLOCK_TEXT, "tb_power": x["tb_power"]}
                questions = {k: {"type": "choice", "instructions": V1_PAIR_QUESTIONS[k][0], "criteria": PAIR_OPTIONS}
                             for k in keys}
                answers = {}
                for k in keys:
                    field = V1_PAIR_QUESTIONS[k][1]
                    better_x = x[field] > y[field] if k == "higher_reach" else x[field] < y[field]
                    answers[k] = "A" if better_x else "B"
                pid = "~".join(sorted([a["design_id"], b["design_id"]]))
                rec = {"test": "dataset_v1", "request": "pair", "question_id": f"dataset_v1:pair:{pid}:{order}",
                       "design_id": pid, "base_design_id": f"revold_{problem}", "source": "revolution_old",
                       "group": "revold", "split": split_of(f"revold_{problem}"), "state": state,
                       "questions": questions, "correct_answer": answers,
                       "evidence": {k: {"field": V1_PAIR_QUESTIONS[k][1], "a": x[V1_PAIR_QUESTIONS[k][1]],
                                        "b": y[V1_PAIR_QUESTIONS[k][1]], "ratio": keys[k]} for k in keys}}
                rec["est_tokens"] = est_tokens({"state": state, "q": questions})
                rec["over_token_limit"] = rec["est_tokens"] > TOKEN_LIMIT
                records.append(rec)
    n_q = Counter(k for rec in records for k in rec["questions"])
    stats = {"requests": dict(Counter(rec["request"] for rec in records)), "questions": dict(n_q),
             "questions_total": sum(n_q.values()), "pairs": n_pairs, "skipped": dict(skipped),
             "designs": len({rec["design_id"] for rec in records if rec["request"] != "pair"})}
    return records, stats


def datacard(records, stats):
    """A short Markdown summary of a dataset_v1 file: what a reader checks first."""
    lines = ["# Data card: dataset_v1", "",
             f"- Designs: {stats['designs']}. Requests: {len(records)}. Questions: {stats['questions_total']}.",
             f"- Requests per kind: {stats['requests']}.", f"- Questions per key: {stats['questions']}.",
             f"- Pairs: {stats['pairs']} (each in two orders).", f"- Skipped: {stats['skipped']}.", "",
             "| Group | Designs | basic | reason | performance | pair |", "|---|---|---|---|---|---|"]
    by_group = defaultdict(lambda: Counter())
    designs = defaultdict(set)
    for r in records:
        by_group[r.get("group")][r["request"]] += 1
        if r["request"] != "pair":
            designs[r.get("group")].add(r["design_id"])
    for g in sorted(by_group, key=str):
        c = by_group[g]
        lines.append(f"| {g} | {len(designs[g])} | {c['basic']} | {c['reason']} | {c['performance']} | {c['pair']} |")
    lines += ["", "Correct answers per question key (all splits):", ""]
    answers = defaultdict(Counter)
    for r in records:
        for k, v in r["correct_answer"].items():
            answers[k][str(v)] += 1
    for k in sorted(answers):
        lines.append(f"- `{k}`: {dict(sorted(answers[k].items()))}")
    splits = Counter(r["split"] for r in records)
    toks = sorted(r["est_tokens"] for r in records)
    lines += ["", f"- Split (requests): {dict(splits)}.",
              f"- Estimated tokens per request: median {toks[len(toks) // 2] if toks else 0}, "
              f"maximum {toks[-1] if toks else 0}; above 8,000: {sum(t > TOKEN_LIMIT for t in toks)}.", ""]
    return "\n".join(lines)


BUILDERS = {"dataset_v1": build_dataset_v1, "area_level": build_area_level, "power_level": build_power_level,
            "pair_compare": build_pair_compare, "synth_reason": build_synth_reason,
            "synth_yesno": build_synth_yesno, "timing_yesno": build_timing_yesno}
