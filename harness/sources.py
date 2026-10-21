"""Read the designs of each source as flow.Design objects.

Sources (see notes/DATA.md):
    revolution_designs    the 27 medium designs of REvolution (v0 RTL and power testbench)
    revolution_variants   the verified variants of one REvolution design
    metrex                the 25,868 MetRex modules
    verilogeval           the 156 VerilogEval reference designs
    rtllm_verified        the 50 RTLLM reference designs
    rtllm_llm             the 290 RTLLM files written by GPT-3.5 and GPT-4
"""
import csv
import datetime
import glob
import hashlib
import json
import re
from pathlib import Path

from . import netlist, paths
from .flow import Design

COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
MODULE_RE = re.compile(r"^\s*module\s+([A-Za-z_]\w*)", re.M)
INSTANCE_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*(?:#\s*\(.*?\)\s*)?([A-Za-z_]\w*)\s*\(", re.M | re.S)
EDGE_RE = re.compile(r"\b(?:posedge|negedge)\s+([A-Za-z_]\w*)")
INPUT_RE = re.compile(r"\binput\b((?:\s*(?:wire|reg|logic|signed|unsigned|\[[^\]]*\]))*\s*"
                      r"[A-Za-z_]\w*(?:\s*,\s*(?!(?:input|output|inout)\b)[A-Za-z_]\w*)*)")
CLOCK_NAME_RE = re.compile(r"^(?:i_|in_)?(?:clk|clock|aclk|sysclk|sys_clk|clk_in|clock_in)(?:_i|_in)?$",
                           re.I)
WORD_RE = re.compile(r"[A-Za-z_]\w*")
NOT_NAMES = {"input", "output", "inout", "wire", "reg", "logic", "signed", "unsigned"}


def strip_comments(text):
    return COMMENT_RE.sub(" ", text)


def find_top(text):
    """Return the module that no other module in the text instantiates, or None if not one."""
    code = strip_comments(text)
    defined = MODULE_RE.findall(code)
    if not defined:
        return None
    used = {m.group(1) for m in INSTANCE_RE.finditer(code) if m.group(1) in defined}
    tops = [m for m in dict.fromkeys(defined) if m not in used]
    return tops[0] if len(tops) == 1 else None


def module_text(text, name):
    code = strip_comments(text)
    m = re.search(rf"^\s*module\s+{re.escape(name)}\b", code, re.M)
    if not m:
        return ""
    end = code.find("endmodule", m.end())
    return code[m.start():end if end > 0 else len(code)]


def input_names(text, top):
    """Return the input port names of the top module, from the RTL text."""
    body = module_text(text, top)
    names = []
    for m in INPUT_RE.finditer(body):
        for word in WORD_RE.findall(re.sub(r"\[[^\]]*\]", " ", m.group(1))):
            if word in ("output", "inout"):
                break         # a list such as 'input d, output reg q' ends at 'output'
            if word not in NOT_NAMES and word not in names:
                names.append(word)
    return names


def guess_clock(text, top):
    """Guess the clock port of the top module from the RTL. Return "" if none.

    The guess is an input that is the subject of posedge or negedge and that is not a reset. The
    labeling step checks the guess against the CLK pins in the netlist (netlist.clocks_and_resets).
    """
    inputs = input_names(text, top)
    edged = [n for n in dict.fromkeys(EDGE_RE.findall(module_text(text, top))) if n in inputs]
    candidates = [n for n in edged if not netlist.RESET_NAME_RE.match(n)]
    named = [n for n in candidates if CLOCK_NAME_RE.match(n)]
    if named:
        return named[0]
    if len(candidates) == 1:
        return candidates[0]
    return ""


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


# ---------------------------------------------------------------- REvolution

def _config_value(config_text, key):
    m = re.search(rf'^{key}="([^"]*)"', config_text, re.M)
    return m.group(1) if m else ""


def revolution_designs():
    """Return the 27 medium designs of REvolution as Design objects with meta["tb_template"].

    The primary file (the top) is last. The other files keep the order of MANIFEST.csv.
    """
    base = paths.REVOLUTION_DIR / "Medium_designs_all"
    out = []
    with open(base / "MANIFEST.csv") as f:
        for row in csv.DictReader(f):
            key = row["key"]
            folder = base / key
            names = [n.replace("[PRIMARY]", "").strip() for n in row["files"].split("|")]
            primary = row["primary"]
            ordered = [n for n in names if n != primary] + [primary]
            files = [(n, (folder / n).read_text(errors="replace")) for n in ordered]
            config = (folder / "config.sh").read_text()
            tb = folder / "tb" / f"tb_pt_{key}.sv"
            out.append(Design(
                design_id=f"rev_{key}_v0", top=row["top"], files=files,
                clock_port=_config_value(config, "CLOCK_PORT"), source="revolution",
                meta={"key": key, "variant": "v0", "primary": primary, "split": row["split"],
                      "tb_template": str(tb) if tb.exists() else ""}))
    return out


REVOLUTION_RECORD_GLOBS = [
    "Test_data_test_designs/*/runs/*/*/test_data.jsonl",
    "RERUN/*/runs/*/*/test_data.jsonl",
    "Train_data_medium_clusters/gpt55_corpus/*/runs/*/*/train_data.jsonl",
]


def _verified(record):
    """True if the REvolution loop verified this record (see notes/DATA.md)."""
    if record.get("event") not in ("iteration", "v0_baseline"):
        return False
    if record.get("flow_error") not in (None, ""):
        return False
    if "gate_verify" in record:
        if record.get("verify_method") == "accuracy":
            return False      # the MX designs: the function of the variants differs
        return record.get("gate_verify") is True and record.get("sec_pass") is not False \
            and not record.get("vacuous")
    # The training corpus has no gate_verify field. Its loop sets these two outcomes only after
    # the verification passed (train_data_loop.py, out.ok).
    return record.get("outcome") in ("accepted", "rejected (no improvement)")


# MV's REvolution runs are still running. So the harness uses only the record files of runs that
# started before the cutoff and that did not change after it. Then the pool of variants stays the
# same over time.
REVOLUTION_CUTOFF = "20261009_000000"
REVOLUTION_CUTOFF_EPOCH = datetime.datetime(2026, 10, 9, 0, 0, 0).timestamp()


def _record_files():
    files = []
    for pattern in REVOLUTION_RECORD_GLOBS:
        for path in sorted(glob.glob(str(paths.REVOLUTION_DIR / pattern))):
            started = Path(path).parent.name            # runs/<design>/<YYYYMMDD_HHMMSS>/
            if not re.fullmatch(r"\d{8}_\d{6}", started) or started >= REVOLUTION_CUTOFF:
                continue
            if Path(path).stat().st_mtime >= REVOLUTION_CUTOFF_EPOCH:
                continue
            files.append(path)
    return files


def _read_records(path):
    rows = []
    for line in open(path, errors="replace"):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def revolution_variants(base_design):
    """Return (v0, variants) for one REvolution design.

    v0        the v0 that the runs of this design used. The loop verified each variant against
              the v0 of its own run, so v0 is the reference. It can differ from the file in
              Medium_designs_all: for tv80, that file also holds the unused tv80 core.
    variants  the distinct verified variants of the runs whose v0 is this v0, v0 excluded

    Each design is base_design with the primary file replaced. For a design with one file, the
    record can name that file differently (tv80: tv80_alu.v), and the one file is replaced.
    meta["rev_metrics"] holds the REvolution metrics (NanGate 45nm, 0.1 ns target): only for the
    selection of pairs, never a correct answer.
    """
    key = base_design.meta["key"]
    primary = base_design.meta["primary"]
    single = len(base_design.files) == 1
    runs = []
    for path in _record_files():
        rows = [r for r in _read_records(path) if r.get("design") == key]
        if rows:
            runs.append((path, rows))
    v0_texts = {}
    counts = {}
    for _path, rows in runs:
        for r in rows:
            if r.get("event") == "v0_baseline":
                code = r.get("rtl") or r.get("code") or ""
                h = sha(code)
                v0_texts[h] = code
                counts[h] = counts.get(h, 0) + 1
    if not counts:
        return base_design, []
    v0_hash = max(counts, key=counts.get)

    def with_primary(code):
        return [(n, code if (n == primary or single) else t) for n, t in base_design.files]

    v0 = Design(design_id=f"rev_{key}_v0", top=base_design.top, files=with_primary(v0_texts[v0_hash]),
                clock_port=base_design.clock_port, source="revolution",
                meta=dict(base_design.meta, variant="v0", v0_sha=v0_hash, v0_runs=counts[v0_hash],
                          v0_from_runs=True))
    seen = {v0_hash}
    variants = []
    for path, rows in runs:
        run_v0 = [r for r in rows if r.get("event") == "v0_baseline"]
        if not run_v0 or sha(run_v0[0].get("rtl") or run_v0[0].get("code") or "") != v0_hash:
            continue
        for r in rows:
            if r.get("event") != "iteration" or not _verified(r):
                continue
            code = r.get("code") or ""
            if not code or not (single or r.get("primary_file") in (None, primary)):
                continue
            h = sha(code)
            if h in seen:
                continue
            seen.add(h)
            variants.append(Design(
                design_id=f"rev_{key}_{h[:12]}", top=base_design.top, files=with_primary(code),
                clock_port=base_design.clock_port, source="revolution",
                meta={"key": key, "variant": h[:12], "primary": primary, "v0_sha": v0_hash,
                      "tb_template": base_design.meta["tb_template"], "record_file": path,
                      "record_iter": r.get("iter"), "rev_metrics": r.get("metrics"),
                      "verify_method": r.get("verify_method") or "differential (training loop)"}))
    return v0, variants


# ---------------------------------------------------------------- public datasets

def metrex(limit=None):
    """Yield the MetRex modules as Design objects. meta["sky130_area"] is only for selection."""
    total_re = re.compile(r"[Tt]otal area[^0-9]*([0-9][0-9,]*(?:\.[0-9]+)?)")
    with open(paths.METREX_FILE) as f:
        for i, line in enumerate(f):
            if limit is not None and i >= limit:
                return
            r = json.loads(line)
            rtl = r["RTL"]
            top = find_top(rtl)
            m = list(total_re.finditer(r["area"]))
            yield Design(
                design_id=f"metrex_{i:05d}", top=top or "", files=[(f"metrex_{i:05d}.v", rtl)],
                clock_port=guess_clock(rtl, top) if top else "", source="metrex",
                meta={"index": i, "sky130_area": float(m[-1].group(1).replace(",", "")) if m else None})


def verilogeval():
    out = []
    for path in sorted(paths.VERILOGEVAL_DIR.glob("*_ref.sv")):
        text = path.read_text()
        prob = path.name[:-len("_ref.sv")]
        out.append(Design(design_id=f"ve_{prob}", top="RefModule", files=[(f"{prob}.sv", text)],
                          clock_port=guess_clock(text, "RefModule"), source="verilogeval",
                          meta={"problem": prob}))
    return out


def _safe(name):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name)


def rtllm_verified():
    out = []
    for path in sorted(paths.RTLLM_DIR.glob("*/*/*/verified_*.v")):
        if "/_" in str(path.relative_to(paths.RTLLM_DIR)):
            continue
        text = path.read_text(errors="replace")
        top = find_top(text) or ""
        name = path.parent.name
        out.append(Design(design_id=f"rtllm_{_safe(name)}", top=top, files=[(_safe(path.name), text)],
                          clock_port=guess_clock(text, top) if top else "", source="rtllm",
                          meta={"design": name, "path": str(path)}))
    return out


def rtllm_llm():
    out = []
    for path in sorted(paths.RTLLM_DIR.glob("_chatgpt*/t*/*.v")):
        text = path.read_text(errors="replace")
        top = find_top(text) or ""
        model, trial = path.parts[-3], path.parts[-2]
        did = f"rtllm_{model.strip('_')}_{trial}_{_safe(path.stem)}"
        out.append(Design(design_id=did, top=top, files=[(_safe(path.name), text)],
                          clock_port=guess_clock(text, top) if top else "", source="rtllm_llm",
                          meta={"model": model, "trial": trial, "path": str(path)}))
    return out
