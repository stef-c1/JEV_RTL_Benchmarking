"""Design plans: fixed, seeded lists of designs for the label jobs.

The same plan name always gives the same designs in the same order. Thus a stopped run continues
with the same list, and a pilot is the first part of the same list.
"""
import json
import math
import random
import re

from . import labels, mutate, paths, sources
from .flow import Design

SEED = 20261009
CHARS_PER_TOKEN = 2.68      # median of MetRex with the Qwen3.5 tokenizer (notes/DATA.md)
JEV_STATE_TOKENS = 30000    # below the Jev limit of 32k tokens for the state plus the longest question


def _est_tokens(chars):
    return chars / CHARS_PER_TOKEN


def _rev_sizes(v0):
    """Return (characters of the RTL, characters of the power testbench) of a REvolution design."""
    rtl = sum(len(t) + 40 for _, t in v0.files)
    tb = v0.meta.get("tb_template")
    return rtl, (len(open(tb).read()) if tb else 0)


def example():
    """MV's flow example mac_int8, with its own power testbench. It checks the harness against
    ./run_all.sh of the flow (159.547393 um2, +1437.97 ps, 0.1038 mW at 500 MHz)."""
    rtl = paths.FLOW_DIR / "rtl"
    files = [(n, (rtl / n).read_text()) for n in ("mult_signed8.v", "acc_signed32.v", "mac_int8.v")]
    return [Design("flow_example_mac_int8", "mac_int8", files, "clk_i", "flow_example",
                   {"tb_file": str(paths.FLOW_DIR / "tb" / "tb_power_mac_int8.sv"),
                    "dut_instance": "dut"})]


def probes(names=None):
    """The DC probes of 2026-10-09 as designs. They check synthcheck on logs of the real flow."""
    rows = [json.loads(l) for l in open(paths.PROJECT_DIR / "probes" / "synth_probe_logs.jsonl")]
    out = []
    for r in rows:
        if names and r["probe"] not in names:
            continue
        out.append(Design(f"probe_{r['probe']}", "top", [(f"{r['probe']}.sv", r["source"])], "",
                          "probe", {"probe": r["probe"]}))
    return out


def _spread(variants, key, k):
    """Return up to k variants at evenly spaced ranks of key (a REvolution metric)."""
    have = [v for v in variants if (v.meta.get("rev_metrics") or {}).get(key)]
    have.sort(key=lambda v: v.meta["rev_metrics"][key])
    if len(have) <= k:
        return have
    idx = sorted({round(i * (len(have) - 1) / (k - 1)) for i in range(k)})
    return [have[i] for i in idx]


def revolution_pairs(per_large_design=30):
    """The REvolution designs for pair_compare (area and power).

    For each design: the v0 of its runs, and its variants. A design with more than 2 x
    per_large_design variants (controller, uart, tv80) gets up to per_large_design variants at
    evenly spaced ranks of the REvolution area, and as many of the REvolution power. These
    REvolution values only spread the selection. The labels come from MV's flow.
    """
    out = []
    for base in sources.revolution_designs():
        if base.meta["key"] == "fifo":
            continue      # two clocks (clk_in, clk_out): not supported by the power step
        v0, variants = sources.revolution_variants(base)
        if not variants:
            continue
        rtl, tb = _rev_sizes(v0)
        if _est_tokens(2 * rtl + tb + 900) > JEV_STATE_TOKENS:
            continue      # a pair of this design does not fit in one Jev request (fft_oc, jpeg_dct, pcie)
        if len(variants) > 2 * per_large_design:
            chosen = {v.design_id: v for v in _spread(variants, "area", per_large_design)}
            chosen.update({v.design_id: v for v in _spread(variants, "mean_power", per_large_design)})
            variants = sorted(chosen.values(), key=lambda v: v.design_id)
        out.append(v0)
        out.extend(variants)
    return out


def _sky130_level(design):
    a = design.meta.get("sky130_area")
    if not a:
        return None
    ge = a / 3.75     # the area of nand2_1 in the MetRex text is 3.75 um2
    return 1 if ge < 1e2 else 2 if ge < 1e3 else 3 if ge < 1e4 else 4 if ge < 1e5 else 5


def area_power_candidates(per_level=160, memory_cap=0.25, max_tokens_chars=18000):
    """Candidates for area_level and power_level, drawn with a fixed seed.

    MetRex: per_level designs for each Sky130 level, with at most memory_cap register-array
    memories per level, and at most max_tokens_chars characters (about 6,700 tokens at 2.68
    characters per token). Then all VerilogEval and RTLLM reference designs, and the REvolution
    v0 designs. The labels come from MV's flow, so a design can land in another level.
    """
    rng = random.Random(SEED)
    by_level = {L: [] for L in range(1, 6)}
    for d in sources.metrex():
        if not d.top or len(d.files[0][1]) > max_tokens_chars:
            continue
        L = _sky130_level(d)
        if L:
            by_level[L].append(d)
    mem_re = re.compile(r"\breg\b[^;]*\]\s*\w+\s*\[[^\]]+\]")
    out = []
    for L in range(1, 6):
        pool = by_level[L]
        rng.shuffle(pool)
        mem = [d for d in pool if mem_re.search(d.files[0][1])]
        non = [d for d in pool if not mem_re.search(d.files[0][1])]
        n_mem = min(len(mem), int(math.floor(per_level * memory_cap)))
        pick = non[:per_level - n_mem] + mem[:n_mem]
        for d in pick:
            d.meta["sky130_level"] = L
        out.extend(pick)
    out.extend(sources.verilogeval())
    out.extend(sources.rtllm_verified())
    for base in sources.revolution_designs():
        if base.meta["key"] == "fifo":
            continue
        v0, _ = sources.revolution_variants(base)
        rtl, tb = _rev_sizes(v0)
        if _est_tokens(rtl + tb + 600) > JEV_STATE_TOKENS:
            continue      # the design does not fit in one Jev request (fft_oc, jpeg_dct)
        out.append(v0)
    return out


def synth_base(metrex_n=300):
    """Base designs for synth_yesno and synth_reason: VerilogEval, RTLLM, the 27 REvolution v0
    designs, and a seeded sample of metrex_n MetRex designs (each at most 18,000 characters)."""
    rng = random.Random(SEED)
    out = sources.verilogeval() + sources.rtllm_verified()
    for base in sources.revolution_designs():
        v0, _ = sources.revolution_variants(base)
        if _est_tokens(_rev_sizes(v0)[0] + 400) > JEV_STATE_TOKENS:
            continue      # the design does not fit in one Jev request (jpeg_dct)
        out.append(v0)
    pool = [d for d in sources.metrex() if d.top and len(d.files[0][1]) <= 18000]
    pool.sort(key=lambda d: d.design_id)
    rng.shuffle(pool)
    out.extend(pool[:metrex_n])
    return out


def rtllm_llm():
    """The 290 RTLLM files of GPT-3.5 and GPT-4: natural cases for synth_yesno and synth_reason."""
    return [d for d in sources.rtllm_llm() if d.top]


def _synthesizing_bases():
    """The base designs of synth_base that DC synthesizes (the synth labels must exist)."""
    path = labels.label_file("synth")
    if not path.exists():
        raise SystemExit("no synth labels: first run  python3.12 -m harness label synth --plan synth_base")
    ok, seen = {}, set()
    for line in open(path):
        r = json.loads(line)
        seen.add(r["design_id"])
        if r["synth"]["synthesizes"] and not r["design_id"].startswith(("mut_", "trap_", "probe_")):
            ok[r["design_id"]] = r
    plan = get("synth_base")
    missing = [d.design_id for d in plan if d.design_id not in seen]
    if missing:
        raise SystemExit(f"{len(missing)} designs of synth_base have no synth record yet. Finish "
                         "python3.12 -m harness label synth --plan synth_base first.")
    return [d for d in plan if d.design_id in ok]


def synth_mutants(per_class=80):
    """Mutants for synth_reason (notes/synth_reason.md): up to per_class mutants per class, each from
    another base design. The edit goes into the file of the top module (the last file).

    The builder keeps a mutant only if DC shows the intended class, so per_class is larger than
    the 50 questions per class of the test.
    """
    bases = _synthesizing_bases()
    rng = random.Random(SEED + 1)
    out = []
    for cls in mutate.TEMPLATES:
        order = list(bases)
        rng.shuffle(order)
        n = 0
        for i, base in enumerate(order):
            if n >= per_class:
                break
            name, text = base.files[-1]
            res = mutate.mutate(text, cls, seed=SEED + i, template_index=n)
            if not res:
                continue
            new_text, template, desc = res
            files = base.files[:-1] + [(name, new_text)]
            out.append(Design(f"mut_{cls}_{n:03d}_{base.design_id}"[:120], base.top, files, "",
                              base.source, {"intended": cls, "template": template, "edit": desc,
                                            "base_design_id": base.design_id}))
            n += 1
    return out


def synth_traps(pairs=60):
    """Trap pairs for synth_yesno: on one base design, a trap edit that DC accepts and a twin edit
    of the same kind that DC rejects (mutate.TRAP_TEMPLATES)."""
    bases = _synthesizing_bases()
    rng = random.Random(SEED + 2)
    order = list(bases)
    rng.shuffle(order)
    out = []
    kinds = list(mutate.TRAP_TEMPLATES)
    n = 0
    for i, base in enumerate(order):
        if n >= pairs:
            break
        kind = kinds[n % len(kinds)]
        trap, (twin_cls, twin) = mutate.TRAP_TEMPLATES[kind]
        name, text = base.files[-1]
        masked = mutate.blank_comments(text)
        a = trap(text, masked, random.Random(SEED + i))
        b = twin(text, masked, random.Random(SEED + i))
        if not a or not b:
            continue
        for side, (new_text, desc), intended in (("trap", a, None), ("twin", b, twin_cls)):
            out.append(Design(f"trap_{kind}_{n:03d}_{side}_{base.design_id}"[:120], base.top,
                              base.files[:-1] + [(name, new_text)], "", base.source,
                              {"trap_kind": kind, "side": side, "pair": n, "intended": intended,
                               "edit": desc, "base_design_id": base.design_id}))
        n += 1
    return out


def timing(n_designs=160, min_ge=10.0):
    """Designs for timing_yesno: a seeded sample of the ppa labels with status ok and at least
    min_ge GE. The clock port is the one that the ppa job used (checked in the netlist)."""
    path = labels.label_file("ppa")
    if not path.exists():
        raise SystemExit("no ppa labels: first run  python3.12 -m harness label ppa --plan area_power")
    labeled = {json.loads(l)["design_id"] for l in open(path)}
    missing = [d.design_id for d in get("area_power") if d.design_id not in labeled]
    if missing:
        raise SystemExit(f"{len(missing)} designs of area_power have no ppa record yet. Finish "
                         "python3.12 -m harness label ppa --plan area_power first.")
    rows = []
    for line in open(path):
        r = json.loads(line)
        if r.get("status") == "ok" and r.get("area_um2") and r["area_um2"] / paths.GE_UM2 >= min_ge \
                and r.get("source") != "flow_example":
            if r.get("source") == "revolution" and (r.get("meta") or {}).get("variant") != "v0":
                continue
            if r.get("source") == "revolution_old":
                continue      # these candidates are only for pair_compare
            rows.append(r)
    rows.sort(key=lambda r: r["design_id"])
    random.Random(SEED + 3).shuffle(rows)
    return [Design(r["design_id"], r["top"], [tuple(f) for f in r["files"]], r.get("clock_port") or "",
                   r["source"], r.get("meta") or {}) for r in rows[:n_designs]]


def _revold_groups():
    """The passing old REvolution candidates per problem, and a seeded sample of failing ones."""
    from . import revolution_old
    groups = {}
    failed, seen_failed = [], 0
    rng = random.Random(SEED + 4)
    for rec in revolution_old.load_index():
        if rec["passed"] and (rec.get("ppa_ng45") or {}).get("area"):
            groups.setdefault((rec["bench"], rec["problem"]), []).append(rec)
        elif not rec["passed"]:
            seen_failed += 1          # a reservoir sample of 200 failing candidates
            if len(failed) < 200:
                failed.append(rec)
            elif rng.random() < 200 / seen_failed:
                failed[rng.randrange(200)] = rec
    return groups, failed


def revold_pairs_sample(n_rtllm=5, n_ve=3, per_problem=4):
    """A small sample of the old REvolution candidates for the ppa job: per problem, per_problem
    passing candidates at evenly spaced ranks of their REvolution area (NanGate 45nm). All
    candidates of one problem share one power testbench (tb_group)."""
    from . import revolution_old
    groups, _ = _revold_groups()
    rng = random.Random(SEED + 5)
    out = []
    for bench, n, min_distinct in (("RTLLM", n_rtllm, 5), ("VerilogEval-Spec-to-RTL", n_ve, 3)):
        keys = sorted(k for k, v in groups.items() if k[0] == bench
                      and len({round(r["ppa_ng45"]["area"], 3) for r in v}) >= min_distinct)
        rng.shuffle(keys)
        for key in keys[:n]:
            by_area = {}
            for r in sorted(groups[key], key=lambda r: r["sha"]):
                by_area.setdefault(round(r["ppa_ng45"]["area"], 3), r)
            ordered = [by_area[a] for a in sorted(by_area)]
            idx = sorted({round(i * (len(ordered) - 1) / (per_problem - 1)) for i in range(per_problem)})
            for i in idx:
                out.append(revolution_old.candidate_design(ordered[i], tb_group=f"revold_{key[1]}"))
    return out


def revold_failed_sample(n=16):
    """A seeded sample of n old REvolution candidates that failed in REvolution, for the synth job."""
    from . import revolution_old
    _, failed = _revold_groups()
    failed.sort(key=lambda r: r["sha"])
    random.Random(SEED + 6).shuffle(failed)
    return [revolution_old.candidate_design(r) for r in failed[:n]]


def revold_pairs(per_problem=6, min_distinct=3):
    """The full plan of old REvolution candidates for pair_compare: per problem with at least
    min_distinct distinct REvolution areas, per_problem passing candidates at evenly spaced ranks
    of the area (about 717 designs in 133 problems)."""
    from . import revolution_old
    groups, _ = _revold_groups()
    out = []
    for key in sorted(groups):
        by_area = {}
        for r in sorted(groups[key], key=lambda r: r["sha"]):
            by_area.setdefault(round(r["ppa_ng45"]["area"], 3), r)
        if len(by_area) < min_distinct:
            continue
        ordered = [by_area[a] for a in sorted(by_area)]
        k = min(per_problem, len(ordered))
        idx = sorted({round(i * (len(ordered) - 1) / (k - 1)) for i in range(k)})
        out.extend(revolution_old.candidate_design(ordered[i], tb_group=f"revold_{key[1]}") for i in idx)
    return out


def revold_failed(n=600):
    """A seeded sample of n distinct old REvolution candidates that failed in REvolution, for the
    synth job: natural LLM cases for synth_yesno and synth_reason. The sample holds the same
    number of candidates from each benchmark where possible."""
    from . import revolution_old
    rng = random.Random(SEED + 7)
    by_bench = {}
    for rec in revolution_old.load_index():
        # A file with a Markdown fence is raw LLM text, not RTL (5,372 failed candidates), so a
        # question on it would be trivial.
        if not rec["passed"] and "```" not in rec["rtl"]:
            by_bench.setdefault(rec["bench"], []).append({"sha": rec["sha"], "bench": rec["bench"],
                                                          "problem": rec["problem"]})
    picked = []
    for bench in sorted(by_bench):
        pool = sorted(by_bench[bench], key=lambda r: r["sha"])
        rng.shuffle(pool)
        picked.extend(pool[:n // len(by_bench)])
    wanted = {r["sha"] for r in picked}
    out = []
    for rec in revolution_old.load_index():
        if not rec["passed"] and rec["sha"] in wanted:
            out.append(revolution_old.candidate_design(rec))
    out.sort(key=lambda d: d.design_id)
    return out


def revolution_spread_check(per_design=9):
    """A check of the new REvolution variants: the v0 and per_design variants each of controller,
    uart, and tv80, at evenly spaced ranks of the REvolution area. The designs come from the frozen
    plan revolution_pairs, so their labels count for that plan too."""
    pool = get("revolution_pairs")
    out = []
    for key in ("controller", "uart", "tv80"):
        group = [d for d in pool if d.meta.get("key") == key]
        v0 = [d for d in group if d.meta.get("variant") == "v0"]
        rest = sorted((d for d in group if d.meta.get("variant") != "v0"),
                      key=lambda d: (d.meta.get("rev_metrics") or {}).get("area") or 0)
        if len(rest) > per_design:
            idx = sorted({round(i * (len(rest) - 1) / (per_design - 1)) for i in range(per_design)})
            rest = [rest[i] for i in idx]
        out.extend(v0 + rest)
    return out


def _tag(designs, group):
    for d in designs:
        d.meta = dict(d.meta, group=group)
    return list(designs)


def _chars(d):
    tb = d.meta.get("tb_template")
    return sum(len(t) for _, t in d.files) + (len(open(tb).read()) if tb else 0)


def dataset_v1():
    """The design-centric dataset v1 (MV, 2026-10-13): one test = one design, and each design gets
    one vlog run and one flow run at 500 MHz (job "design"). About 150 designs:

      metrex        8 MetRex designs per Sky130 level 1 to 5 (from the frozen area_power plan)
      revolution    the 10 smallest REvolution v0 designs (they fit the Kev limit with the testbench)
      reference     10 RTLLM verified designs and 5 sequential VerilogEval reference designs
      revold        the 32 old REvolution candidates of the sample (8 problems x 4): pair questions
      mutant        2 mutants per synth_reason class, each on its own base design of the groups above
      natural       10 old REvolution candidates that failed in REvolution, and 10 RTLLM LLM files
      trap          2 trap pairs per trap kind (a DC-accepted edit and a rejected twin)
    """
    rng = random.Random(SEED + 10)
    ap = get("area_power")
    out = []
    for L in range(1, 6):
        out += _tag([d for d in ap if d.source == "metrex" and d.meta.get("sky130_level") == L][:8], "metrex")
    # lstm, cnn, and cpu_rrw had no usable REvolution run. The power simulation of lstm wrote a VCD of
    # 8.85 GB (2026-10-13), so these three designs are not in the dataset.
    rev = sorted((d for d in ap if d.source == "revolution" and d.meta.get("key") not in ("lstm", "cnn", "cpu_rrw")),
                 key=_chars)[:10]
    out += _tag(rev, "revolution")
    rtllm = sorted(sources.rtllm_verified(), key=lambda d: d.design_id)
    rng.shuffle(rtllm)
    ve = sorted((d for d in sources.verilogeval() if d.clock_port), key=lambda d: d.design_id)
    rng.shuffle(ve)
    refs = _tag(rtllm[:10], "reference") + _tag(ve[:5], "reference")
    out += refs
    out += _tag(revold_pairs_sample(), "revold")
    # Mutants and traps: each on its own base design (references, REvolution v0, MetRex levels 2-3).
    bases = refs + rev + [d for d in out if d.meta.get("group") == "metrex" and d.meta.get("sky130_level") in (2, 3)]
    order = list(bases)
    rng.shuffle(order)
    used = set()
    mutants = []
    for cls in mutate.TEMPLATES:
        n = 0
        for i, base in enumerate(order):
            if n >= 2:
                break
            if base.design_id in used:
                continue
            name, text = base.files[-1]
            res = mutate.mutate(text, cls, seed=SEED + 100 + i, template_index=n)
            if not res:
                continue
            new_text, template, desc = res
            used.add(base.design_id)
            mutants.append(Design(f"mut_{cls}_{n}_{base.design_id}"[:120], base.top,
                                  base.files[:-1] + [(name, new_text)], base.clock_port, base.source,
                                  {"group": "mutant", "intended": cls, "template": template, "edit": desc,
                                   "base_design_id": base.design_id,
                                   "tb_template": base.meta.get("tb_template", "")}))
            n += 1
    out += mutants
    traps = []
    kinds = list(mutate.TRAP_TEMPLATES)
    n = 0
    for i, base in enumerate(order):
        if n >= 2 * len(kinds):
            break
        if base.design_id in used:
            continue
        kind = kinds[n % len(kinds)]
        trap, (twin_cls, twin) = mutate.TRAP_TEMPLATES[kind]
        name, text = base.files[-1]
        masked = mutate.blank_comments(text)
        a = trap(text, masked, random.Random(SEED + 200 + i))
        b = twin(text, masked, random.Random(SEED + 200 + i))
        if not a or not b:
            continue
        used.add(base.design_id)
        for side, (new_text, desc), intended in (("trap", a, None), ("twin", b, twin_cls)):
            traps.append(Design(f"trap_{kind}_{n}_{side}_{base.design_id}"[:120], base.top,
                                base.files[:-1] + [(name, new_text)], base.clock_port, base.source,
                                {"group": "trap", "trap_kind": kind, "side": side, "pair": n,
                                 "intended": intended, "edit": desc, "base_design_id": base.design_id,
                                 "tb_template": base.meta.get("tb_template", "")}))
        n += 1
    out += traps
    from . import revolution_old
    failed = {"RTLLM": [], "VerilogEval-Spec-to-RTL": []}
    for rec in revolution_old.load_index():
        if not rec["passed"] and "```" not in rec["rtl"]:
            failed[rec["bench"]].append(rec)
    nat = []
    for bench in sorted(failed):
        pool = sorted(failed[bench], key=lambda r: r["sha"])
        rng.shuffle(pool)
        nat += [revolution_old.candidate_design(r) for r in pool[:5]]
    llm = sorted((d for d in sources.rtllm_llm() if d.top), key=lambda d: d.design_id)
    rng.shuffle(llm)
    nat += llm[:10]
    out += _tag(nat, "natural")
    # noncompile: 10 designs with one illegal-code edit (a removed ';' or an undeclared name), each on
    # a base design that no mutant or trap uses. They make the compile question less one-sided. They
    # get only the basic request (the reason classes keep 2 mutants each). Added after the groups
    # above, so the choices of those groups do not change.
    templates = mutate.TEMPLATES["illegal_code"]
    n = 0
    for i, base in enumerate(order):
        if n >= 10:
            break
        if base.design_id in used:
            continue
        name, text = base.files[-1]
        res = mutate.mutate(text, "illegal_code", seed=SEED + 300 + i, template_index=n)
        if not res:
            continue
        new_text, template, desc = res
        used.add(base.design_id)
        out.append(Design(f"noncomp_{n}_{base.design_id}"[:120], base.top, base.files[:-1] + [(name, new_text)],
                          base.clock_port, base.source,
                          {"group": "noncompile", "intended": "illegal_code", "template": template, "edit": desc,
                           "base_design_id": base.design_id, "tb_template": base.meta.get("tb_template", "")}))
        n += 1
    ids = [d.design_id for d in out]
    assert len(ids) == len(set(ids)), "duplicate design ids in dataset_v1"
    return out


PLANS = {
    "dataset_v1": dataset_v1,
    "revolution_spread_check": revolution_spread_check,
    "revold_pairs": revold_pairs,
    "revold_failed": revold_failed,
    "revold_pairs_sample": revold_pairs_sample,
    "revold_failed_sample": revold_failed_sample,
    "timing": timing,
    "example": example,
    "probes": probes,
    "revolution_pairs": revolution_pairs,
    "area_power": area_power_candidates,
    "synth_base": synth_base,
    "rtllm_llm": rtllm_llm,
    "synth_mutants": synth_mutants,
    "synth_traps": synth_traps,
}


def frozen_path(name):
    return paths.WORK_DIR / "plans" / f"{name}.jsonl"


def get(name, refresh=False):
    """Return the designs of a plan from its frozen file. Make the file on the first call.

    The frozen file holds each design with its full RTL text, so a later change of a source (for
    example a new REvolution run) does not change the plan. refresh=True makes the file again.
    """
    path = frozen_path(name)
    if path.exists() and not refresh:
        out = []
        for line in open(path):
            r = json.loads(line)
            out.append(Design(r["design_id"], r["top"], [tuple(f) for f in r["files"]], r["clock_port"],
                              r["source"], r["meta"]))
        return out
    designs = PLANS[name]()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".jsonl.tmp")
    with open(tmp, "w") as f:
        for d in designs:
            f.write(json.dumps({"design_id": d.design_id, "top": d.top, "files": d.files,
                                "clock_port": d.clock_port, "source": d.source, "meta": d.meta}) + "\n")
    tmp.replace(path)
    return designs

