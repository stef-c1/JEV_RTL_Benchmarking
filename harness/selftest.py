"""Checks of the harness that need no tool run.

Each check returns (name, passed, detail). Run all checks with:
    python3.12 -m harness selftest
"""
import difflib
import json
from pathlib import Path

from . import flow, paths, synthcheck

PROBE_LOGS = paths.PROJECT_DIR / "probes" / "synth_probe_logs.jsonl"

# The expected result of each DC probe: None means "synthesizes", else the synth_reason class.
# The table is the same as the tables in notes/synth_yesno.md and notes/synth_reason.md.
EXPECTED_PROBES = {
    "c00_clean": None, "c01_display": None, "c02_latch": None, "c03_comb_loop": None,
    "c04_division": None, "c05_assign_delay": None, "c06_nb_delay": None, "c07_initial": None,
    "c08_x_compare": None, "c09_assign_to_reg": None, "p04_delay_stmt": None,
    "p06_multi_event": None, "p09_while_data": None, "p10_for_var_bound": None,
    "p17_hier_ref": None, "p24_task_delay": None, "p30_repeat_var": None,
    "p32_always_no_event": None, "p38_fileio": None,
    "p01_syntax_error": "illegal_code", "p02_undeclared": "illegal_code",
    "p23_proc_to_wire": "illegal_code", "p36_var_part_select": "illegal_code",
    "p11_real": "unsupported_construct", "p18_class": "unsupported_construct",
    "p19_dyn_array": "unsupported_construct", "p20_string": "unsupported_construct",
    "p31_udp": "unsupported_construct", "p33_dpi": "unsupported_construct",
    "p34_trireg": "unsupported_construct", "p39_time_var": "unsupported_construct",
    "p05_wait": "timing_control", "p12_fork": "timing_control", "p25_event": "timing_control",
    "p13_force": "simulation_statement", "p14_random": "simulation_statement",
    "p28_proc_assign": "simulation_statement",
    "p07_both_edges": "event_list", "p16_edge_level_mix": "event_list",
    "p35_negedge_level_reset_mix": "event_list", "p37_mult_in_sens_task": "event_list",
    "p15_async_if_not_top": "async_reset", "p26_two_clocks": "async_reset",
    "p27_async_data_load": "async_reset",
    "p08_multi_driver": "multiple_drivers",
    "p22_mixed_blocking": "mixed_assignments",
    "p21_recursion_var": "unbounded_loop", "p29_forever_no_timing": "unbounded_loop",
    "p03_missing_module": "instance_mismatch", "p40_unknown_port": "instance_mismatch",
    "p41_unknown_param": "instance_mismatch",
}


def vlog_ok_from_log(text):
    """True if a QuestaSim vlog log shows no error."""
    return "** Error" not in text and "Errors: 0" in text


def check_config_render():
    base = (paths.FLOW_DIR / "config.sh").read_text()
    example = flow.Design("mac_int8", "mac_int8",
                          [("mult_signed8.v", ""), ("acc_signed32.v", ""), ("mac_int8.v", "")],
                          "clk_i")
    same = flow.render_config(base, example, flow.PowerTB("tb_power_mac_int8", "", "dut")) == base
    other = flow.Design("x", "control_unit", [("controller.v0.v", "")], "clk")
    out = flow.render_config(base, other, flow.PowerTB("tb_pt_controller", "", "control_unit0"))
    changed = [l for l in difflib.unified_diff(base.splitlines(), out.splitlines(), lineterm="", n=0)
               if l[:1] in "+-" and l[:3] not in ("+++", "---")]
    keys = {l[1:].split("=")[0].strip() for l in changed if "=" in l}
    rtl_lines = [l for l in changed if '"rtl/' in l]
    ok = same and keys == {"DESIGN_NAME", "CLOCK_PORT", "TB_POWER", "DUT_INSTANCE"} and len(rtl_lines) == 4
    return ("config.sh rendering", ok,
            f"example design gives MV's config.sh unchanged: {same}; other design changes only "
            f"{sorted(keys)} and the RTL_FILES list ({len(rtl_lines)} lines)")


def check_classifier():
    rows = [json.loads(l) for l in open(PROBE_LOGS)]
    bad = []
    for r in rows:
        exp = EXPECTED_PROBES[r["probe"]]
        log = r["dc_log"]
        res = synthcheck.classify(log, vlog_ok_from_log(r["vlog_log"]), "Total cell area" in log)
        got = None if res["synthesizes"] else res["reason"]
        if res["synthesizes"] != (exp is None) or got != exp:
            bad.append(f"{r['probe']}: expected {exp}, got {got} {res['classes']}")
    n_yes = sum(1 for v in EXPECTED_PROBES.values() if v is None)
    detail = (f"{len(rows) - len(bad)} of {len(rows)} probes as expected "
              f"({n_yes} synthesize, {len(rows) - n_yes} in one of 10 classes)")
    if bad:
        detail += "; differences: " + "; ".join(bad)
    return ("synthcheck on the 51 DC probes", not bad and len(rows) == len(EXPECTED_PROBES), detail)


FLOW_PROBE_LOGS = paths.PROJECT_DIR / "probes" / "flow_probe_logs.jsonl"


def check_classifier_flow_logs():
    """The same check on logs of MV's real flow (02_synth.sh), which add follow-on errors."""
    rows = [json.loads(l) for l in open(FLOW_PROBE_LOGS)]
    bad = []
    for r in rows:
        exp = r["expected"] if "expected" in r else EXPECTED_PROBES[r["probe"]]
        res = synthcheck.classify(r["dc_log"], vlog_ok_from_log(r["vlog_log"]), r["netlist"])
        got = None if res["synthesizes"] else res["reason"]
        if res["synthesizes"] != (exp is None) or got != exp:
            bad.append(f"{r['probe']}: expected {exp}, got {got} {res['classes']} unknown {res['unknown_errors']}")
    detail = f"{len(rows) - len(bad)} of {len(rows)} real flow logs as expected"
    if bad:
        detail += "; differences: " + "; ".join(bad)
    return ("synthcheck on real flow logs", not bad, detail)


def check_revolution_testbenches():
    """Fill every REvolution power testbench. Each fill must change only the three items of
    tbgen.fill_revolution_tb and must find the design instance."""
    from . import sources, tbgen
    bad, n = [], 0
    for d in sources.revolution_designs():
        t = d.meta.get("tb_template")
        if not t:
            bad.append(f"{d.meta['key']}: no template")
            continue
        text = Path(t).read_text()
        tb = tbgen.fill_revolution_tb(text, d.top)
        changed = [l for l in difflib.unified_diff(text.splitlines(), tb.text.splitlines(), lineterm="", n=0)
                   if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        if len(changed) != 7:      # 3 added guard lines, and 2 x (1 removed + 1 added) lines
            bad.append(f"{d.meta['key']}: {len(changed)} changed lines")
        n += 1
    return ("REvolution power testbenches", not bad,
            f"{n} templates filled, each with the 3 changes only" + ("; " + "; ".join(bad) if bad else ""))


VALIDATION_DIR = paths.VOLUME_DIR / "jev_rtl_work" / "validation"


def check_validation_records():
    """The stored validation records must match the files in their run folders: the testbench in
    the record is the file that the flow simulated, and config.sh differs from MV's config.sh only
    in the design lines."""
    label_path = VALIDATION_DIR / "labels" / "ppa.jsonl"
    if not label_path.exists():
        return ("validation records", True, "no validation records (skipped)")
    base = (paths.FLOW_DIR / "config.sh").read_text()
    bad, n = [], 0
    for line in open(label_path):
        r = json.loads(line)
        run = Path(r["run_dir"])
        tb_file = run / "tb" / f"{r['tb_module']}.sv"
        if not tb_file.exists() or tb_file.read_text() != r["tb_power"]:
            bad.append(f"{r['design_id']}: the testbench file differs from the record")
        cfg = (run / "config.sh").read_text()
        changed = {l[1:].split("=")[0] for l in difflib.unified_diff(base.splitlines(), cfg.splitlines(), lineterm="", n=0)
                   if l[:1] in "+-" and l[:3] not in ("+++", "---") and "=" in l and not l[1:].startswith("    ")}
        if not changed <= {"DESIGN_NAME", "CLOCK_PORT", "TB_POWER", "DUT_INSTANCE"}:
            bad.append(f"{r['design_id']}: config.sh changes {sorted(changed)}")
        n += 1
    return ("validation records", not bad, f"{n} ppa records match their run folders" + ("; " + "; ".join(bad) if bad else ""))


def check_dataset_builder():
    """build_dataset_v1 on synthetic design records: the request kinds and the rules of DATASET.md."""
    import tempfile
    from . import build, labels

    def rec(did, group, synth, reason=None, vlog=True, area=10.0, slack=1500.0, power=2e-5, meta=None,
            source="metrex", tb="tb A"):
        m = dict({"group": group}, **(meta or {}))
        return {"design_id": did, "source": source, "top": "t", "files": [["t.v", "module t; endmodule"]],
                "meta": m, "status": "ok" if synth else "does_not_synthesize", "vlog_ok": vlog,
                "synth": {"synthesizes": synth, "reason": reason, "errors": [], "warnings": [], "classes": [reason] if reason else []},
                "area_um2": area if synth else None, "slack_ps": slack if synth else None, "period_ns": 2.0,
                "reach_mhz": labels.reach(2.0, slack)[1] if synth else None,
                "total_power_w": power if synth else None, "annotation": {"annotated_pct": 100.0} if synth else None,
                "tb_power": tb if synth else None}
    rows = [
        rec("d1", "metrex", True),
        rec("b_bad", "metrex", False, "illegal_code", vlog=False),
        rec("m_ok", "mutant", False, "event_list", meta={"intended": "event_list", "base_design_id": "d1"}),
        rec("m_wrong", "mutant", False, "illegal_code", meta={"intended": "event_list", "base_design_id": "d1"}),
        rec("m_badbase", "mutant", False, "event_list", meta={"intended": "event_list", "base_design_id": "b_bad"}),
        rec("p1", "revold", True, area=10.0, source="revolution_old", meta={"problem": "P"}),
        rec("p2", "revold", True, area=20.0, source="revolution_old", meta={"problem": "P"}),
    ]
    old_dir = paths.LABELS_DIR
    with tempfile.TemporaryDirectory() as tmp:
        labels.paths.LABELS_DIR = Path(tmp)
        try:
            with open(Path(tmp) / "design.jsonl", "w") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")
            records, stats = build.build_dataset_v1()
        finally:
            labels.paths.LABELS_DIR = old_dir
    kinds = {(r["request"], r["design_id"]) for r in records}
    problems = []
    if ("performance", "b_bad") in kinds or ("performance", "m_ok") in kinds:
        problems.append("a performance request for a design that does not synthesize")
    if not {("basic", "m_ok"), ("reason", "m_ok")} <= kinds:
        problems.append("the valid mutant is missing")
    if any(d in ("m_wrong", "m_badbase") for _, d in kinds):
        problems.append("a mutant with a wrong class or a failing base is in the dataset")
    pairs = [r for r in records if r["request"] == "pair"]
    if len(pairs) != 2 or {p["correct_answer"]["smaller_area"] for p in pairs} != {"A", "B"}:
        problems.append(f"the pair is not in both orders with swapped answers: {[p['correct_answer'] for p in pairs]}")
    perf = next(r for r in records if r["request"] == "performance" and r["design_id"] == "d1")
    if "tb_power" not in perf["state"] or set(perf["questions"]) != {"slack", "reach", "area", "power"}:
        problems.append("the performance request of d1 is incomplete")
    basic = next(r for r in records if r["request"] == "basic" and r["design_id"] == "b_bad")
    if "tb_power" in basic["state"] or basic["correct_answer"] != {"compiles": False, "synthesizes": False}:
        problems.append("the basic request of b_bad is wrong")
    return ("dataset builder on synthetic records", not problems,
            f"{len(records)} requests {stats['requests']}" + ("; " + "; ".join(problems) if problems else ""))


CHECKS = [check_config_render, check_classifier, check_classifier_flow_logs,
          check_revolution_testbenches, check_validation_records, check_dataset_builder]


def run_all():
    results = []
    for check in CHECKS:
        try:
            results.append(check())
        except Exception as exc:          # a crash of a check is a failed check
            results.append((check.__name__, False, f"{type(exc).__name__}: {exc}"))
    for name, ok, detail in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    return all(ok for _, ok, _ in results)
