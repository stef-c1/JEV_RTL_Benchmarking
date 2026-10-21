"""The candidates of the REvolution ASP-DAC 2026 runs (REvolution.tar.gz of 2026-05-19).

The archive holds, for 4 LLM configurations (gpt-4.1-mini, deepseek, llama3, llama3_baseline) and
the problems of VerilogEval Spec-to-RTL and RTLLM, about 200 candidates per problem in Gen*/
folders: <problem>_<strategy>_sample<k>.sv, .syn.v, _synthesis_report.ppa, and _thought.txt.

The meaning of the .ppa file: REvolution (src/revolution/algorithm.py) simulates each candidate
with the benchmark testbench first. Only a candidate that passes goes to synthesis, a gate-level
check, and PPA. For Prob031_dff of gpt-4.1-mini, the summary gives 210 candidates and a success
rate of 0.9 for "synthesis_ppa", and the folder has exactly 189 .ppa files (0.9 x 210). Thus a
candidate with a .ppa file passed the testbench (an inference from the code and this count).
A candidate without a .ppa file failed the testbench, the compilation, or the synthesis.

The PPA values are from NanGate 45nm in the REvolution flow. They help only to select candidates.
The labels come from MV's flow.

build_index reads the archive once (streaming) and writes one JSON line per distinct candidate
(per benchmark, problem, and RTL text) to INDEX_FILE.
"""
import hashlib
import json
import re
import tarfile
from collections import defaultdict

from . import paths, sources
from .flow import Design

ARCHIVE = paths.REVOLUTION_DIR / "REvolution.tar.gz"
INDEX_FILE = paths.DATA_DIR / "revolution_aspdac2026_index.jsonl"
NAME_RE = re.compile(r"^REvolution-aspdac2026-paper/exp/([^/]+)_results/([^/]+)/([^/]+)/(Gen\d+)/"
                     r"(.+?)(\.sv|_synthesis_report\.ppa)$")


def _ppa(text):
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    if len(lines) < 2:
        return None
    keys = lines[0].split(",")
    vals = lines[1].split(",")
    out = {}
    for k, v in zip(keys, vals):
        try:
            out[k] = float(v)
        except ValueError:
            out[k] = None
    return out


def build_index(log=print):
    """Read the archive once and write INDEX_FILE. Return the number of distinct candidates."""
    rtl = {}            # (llm, bench, problem, gen, base) -> text
    ppa = {}            # (llm, bench, problem, gen, base) -> metrics
    with tarfile.open(ARCHIVE, "r|gz") as tar:
        for member in tar:
            if not member.isfile():
                continue
            m = NAME_RE.match(member.name)
            if not m:
                continue
            llm, bench, problem, gen, base, kind = m.groups()
            data = tar.extractfile(member).read().decode(errors="replace")
            key = (llm, bench, problem, gen, base)
            if kind == ".sv":
                rtl[key] = data
            else:
                ppa[key] = _ppa(data)
    log(f"read {len(rtl)} candidate RTL files and {len(ppa)} PPA reports")
    groups = defaultdict(dict)     # (bench, problem) -> sha -> record
    for key, text in rtl.items():
        llm, bench, problem, gen, base = key
        h = hashlib.sha256(text.encode()).hexdigest()
        rec = groups[(bench, problem)].get(h)
        if rec is None:
            rec = {"bench": bench, "problem": problem, "sha": h, "rtl": text, "copies": [],
                   "passed": False, "ppa_ng45": None}
            groups[(bench, problem)][h] = rec
        rec["copies"].append({"llm": llm, "gen": gen, "name": base})
        if key in ppa and ppa[key] is not None:
            rec["passed"] = True
            rec["ppa_ng45"] = rec["ppa_ng45"] or ppa[key]
    n = 0
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = INDEX_FILE.with_suffix(".jsonl.tmp")
    with open(tmp, "w") as f:
        for (bench, problem), recs in sorted(groups.items()):
            for h in sorted(recs):
                f.write(json.dumps(recs[h]) + "\n")
                n += 1
    tmp.replace(INDEX_FILE)
    log(f"wrote {n} distinct candidates in {len(groups)} problems to {INDEX_FILE}")
    return n


RTLLM_TOPS_FILE = paths.DATA_DIR / "revolution_rtllm_tops.json"   # from bench/RTLLM of the archive


def top_of(rec):
    """The top module of a candidate: TopModule for VerilogEval, the REvolution map for RTLLM."""
    if rec["bench"] == "VerilogEval-Spec-to-RTL":
        return "TopModule"
    tops = json.load(open(RTLLM_TOPS_FILE))
    return tops.get(rec["problem"]) or sources.find_top(rec["rtl"]) or ""


def candidate_design(rec, tb_group=None):
    """Return a candidate as a Design. tb_group makes all candidates of one problem share one
    power testbench (labels._power_tb)."""
    top = top_of(rec)
    bench = "ve" if rec["bench"].startswith("VerilogEval") else "rtllm"
    did = f"revold_{bench}_{rec['problem']}_{rec['sha'][:12]}"
    meta = {"bench": rec["bench"], "problem": rec["problem"], "sha": rec["sha"],
            "passed_revolution": rec["passed"], "ppa_ng45": rec["ppa_ng45"],
            "llms": sorted({c["llm"] for c in rec["copies"]}), "copies": len(rec["copies"])}
    if tb_group:
        meta["tb_group"] = tb_group
    return Design(did, top, [(f"{rec['problem']}.sv", rec["rtl"])], sources.guess_clock(rec["rtl"], top),
                  "revolution_old", meta)


def load_index():
    with open(INDEX_FILE) as f:
        for line in f:
            yield json.loads(line)


if __name__ == "__main__":
    build_index()
