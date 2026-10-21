"""Run the flow for designs and store the results (the labels).

Three kinds of label jobs:
    synth   does DC synthesize the design (synth_yesno, synth_reason)
    ppa     area, slack, and power at 500 MHz (area_level, power_level, pair_compare)
    period  the slack at other clock periods, and the minimum period T_min (timing_yesno)

Each job writes one JSON record per design to labels/<job>.jsonl. A design that has a record
already is skipped, so a stopped run continues where it stopped. The run folders stay in
runs/<job>/<design_id>/ for review.
"""
import contextlib
import fcntl
import json
import subprocess
import time
from pathlib import Path

from . import flow, netlist, paths, synthcheck, tbgen


def label_file(job):
    return paths.LABELS_DIR / f"{job}.jsonl"


def done_ids(job):
    path = label_file(job)
    if not path.exists():
        return set()
    out = set()
    for line in open(path):
        try:
            out.add(json.loads(line)["design_id"])
        except (json.JSONDecodeError, KeyError):
            continue
    return out


@contextlib.contextmanager
def label_lock(job):
    """Hold the lock of one label file. append_record and reclassify_synth both use it."""
    paths.LABELS_DIR.mkdir(parents=True, exist_ok=True)
    with open(paths.LABELS_DIR / f"{job}.jsonl.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def append_record(job, record):
    """Append one record. The label lock keeps the lines of two processes apart."""
    with label_lock(job):
        with open(label_file(job), "a") as f:
            f.write(json.dumps(record) + "\n")
            f.flush()


def design_record(design):
    return {"design_id": design.design_id, "source": design.source, "top": design.top,
            "files": design.files, "clock_port_given": design.clock_port, "meta": design.meta}


def vlog_check(run_dir):
    """Compile the RTL of a run folder with QuestaSim vlog. Return (ok, the first error line).

    The tool setup comes from the tools/ link of the run folder (MV's setup file).
    """
    run_dir = Path(run_dir)
    files = " ".join(f"rtl/{p.name}" for p in sorted((run_dir / "rtl").iterdir()))
    order = [l.split('"')[1] for l in (run_dir / "config.sh").read_text().splitlines()
             if l.strip().startswith('"rtl/')]
    files = " ".join(order) if order else files
    cmd = ("source tools/questasim_2022.4.rc >/dev/null 2>&1 && rm -rf vlog_work && "
           f"vlib vlog_work >/dev/null && vlog -sv -work vlog_work {files}")
    with flow.tool_lock():
        proc = subprocess.run(["bash", "-c", cmd], cwd=run_dir, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (run_dir / "vlog.log").write_text(proc.stdout)
    errors = [l for l in proc.stdout.splitlines() if l.startswith("** Error")]
    ok = proc.returncode == 0 and not errors and "Errors: 0" in proc.stdout
    return ok, (errors[0] if errors else "")


def _synth_result(run_dir, design):
    log_path = Path(run_dir) / "results" / "2_synth" / "synth.log"
    log = log_path.read_text(errors="replace") if log_path.exists() else ""
    net = Path(run_dir) / "results" / "2_synth" / f"{design.top}_mapped.v"
    return log, net


# ---------------------------------------------------------------- synth

def label_synth(design, dry_run=False):
    """Does DC synthesize the design? Used by synth_yesno and synth_reason.

    The run uses CLOCK_PORT="" (the virtual clock of the flow). Synthesizability does not depend
    on the clock constraint, and a wrong clock guess would add a false error.
    """
    d = flow.Design(design.design_id, design.top, design.files, "", design.source, design.meta)
    run_dir = flow.make_run_dir(paths.RUNS_DIR / "synth" / design.design_id, d)
    rec = design_record(design)
    rec.update(job="synth", run_dir=str(run_dir))
    if dry_run:
        rec["dry_run"] = True
        return rec
    step = flow.run_step(run_dir, "synth")
    vlog_ok, vlog_error = vlog_check(run_dir)
    log, net = _synth_result(run_dir, d)
    result = synthcheck.classify(log, vlog_ok, net.exists())
    rec.update(step=step, vlog_ok=vlog_ok, vlog_error=vlog_error, synth=result,
               area_um2=step["summary"].get("area_um2"))
    return rec


def reclassify_synth():
    """Classify every synth record again from the logs in its run folder. Start no tool.

    Use it after a change of the rules in synthcheck.py. Return (records, records with a change).
    """
    path = label_file("synth")
    if not path.exists():
        return 0, 0
    running = subprocess.run(["pgrep", "-f", "[h]arness label"], stdout=subprocess.PIPE, text=True).stdout.split()
    if running:
        raise SystemExit(f"a 'harness label' process is running (pid {', '.join(running)}). "
                         "Run reclassify after it ends.")
    with label_lock("synth"):
        return _reclassify_locked(path)


def _reclassify_locked(path):
    rows = [json.loads(l) for l in open(path)]
    changed = 0
    for r in rows:
        run_dir = Path(r["run_dir"])
        log = (run_dir / "results" / "2_synth" / "synth.log")
        vlog = run_dir / "vlog.log"
        if not log.exists() or not vlog.exists():
            continue
        vlog_text = vlog.read_text(errors="replace")
        vlog_ok = "** Error" not in vlog_text and "Errors: 0" in vlog_text
        net = run_dir / "results" / "2_synth" / f"{r['top']}_mapped.v"
        new = synthcheck.classify(log.read_text(errors="replace"), vlog_ok, net.exists())
        if new != r.get("synth"):
            changed += 1
            r["synth"] = new
    tmp = path.with_suffix(".jsonl.tmp")
    with open(tmp, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    tmp.replace(path)
    return len(rows), changed


# ---------------------------------------------------------------- ppa

def _power_tb(design, net_text, clock, resets):
    """Return (PowerTB, how) for a design: the filled REvolution template or a new testbench."""
    ready = design.meta.get("tb_file")
    if ready:
        # A testbench that is ready for the flow, for example the example testbench of MV's flow.
        return (flow.PowerTB(Path(ready).stem, Path(ready).read_text(), design.meta["dut_instance"]),
                "ready testbench")
    template = design.meta.get("tb_template")
    if template:
        return tbgen.fill_revolution_tb(Path(template).read_text(), design.top), "revolution_template"
    ports = netlist.ports(net_text, design.top)
    if resets:
        name = sorted(resets)[0]
        reset, active_low, how = name, resets[name]["active_low"], f"netlist {resets[name]['pin']} pin"
    else:
        guess = netlist.reset_by_name([p["name"] for p in ports if p["direction"] == "input"
                                       and p["name"] != clock])
        reset, active_low, how = (guess[0], guess[1], "port name") if guess else (None, True, "none")
    group = design.meta.get("tb_group")
    if group:
        # All designs of one group (the candidates of one problem) use the choice of the first
        # design that reaches this step. Then they get the same testbench text.
        spec_file = paths.WORK_DIR / "tb_groups" / f"{group}.json"
        spec_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(spec_file, "x") as f:
                json.dump({"clock": clock, "reset": reset, "active_low": active_low, "how": how,
                           "first_design": design.design_id}, f)
        except FileExistsError:
            pass
        spec = json.load(open(spec_file))
        clock, reset, active_low = spec["clock"], spec["reset"], spec["active_low"]
        how = f"group {group} ({spec['how']}, first design {spec['first_design']})"
    tb = tbgen.write_tb(design.top, ports, clock, reset, active_low)
    return tb, f"generated (reset: {reset or 'none'}, active_low: {active_low}, from {how})"


def label_ppa(design, freq_mhz=paths.DEFAULT_FREQ_MHZ, dry_run=False, run_subdir="ppa", vlog_ok=True):
    """Area, slack, and power of one design at freq_mhz.

    Steps:
      1. step 2 (synthesis) with the clock port of the design
      2. read the clocks from the CLK pins of the netlist. If the design has no clock port but the
         netlist shows one clock, run step 2 again with that clock.
      3. the power testbench: the REvolution template, or a new one from the netlist ports
      4. step 4 (gate-level simulation and PrimeTime)

    run_subdir is the folder of the run folders (runs/<run_subdir>/<design id>). vlog_ok is the
    result of a vlog run, which separates illegal code from unsupported constructs (synthcheck).
    """
    rec = design_record(design)
    rec.update(job="ppa", freq_mhz=freq_mhz, status="ok", notes=[])
    run_dir = flow.make_run_dir(paths.RUNS_DIR / run_subdir / design.design_id, design)
    rec["run_dir"] = str(run_dir)
    if dry_run:
        rec["dry_run"] = True
        return rec
    work = design
    synth_limit = DESIGN_SYNTH_TIMEOUT_S if run_subdir == "design" else 4 * 3600
    step2 = flow.run_step(run_dir, "synth", freq_mhz, timeout_s=synth_limit)
    log, net = _synth_result(run_dir, work)
    synth = synthcheck.classify(log, vlog_ok, net.exists())
    rec.update(synth_step=step2, synth=synth)
    if not synth["synthesizes"]:
        rec["status"] = "does_not_synthesize"
        return rec
    net_text = net.read_text(errors="replace")
    clocks, resets = netlist.clocks_and_resets(net_text, work.top)
    rec.update(netlist_clocks=clocks, netlist_resets=resets)
    if len(clocks) > 1:
        rec["status"] = "multi_clock"
        return rec
    if clocks and clocks[0] != work.clock_port:
        if work.clock_port:
            rec["status"] = "clock_mismatch"
            rec["notes"].append(f"config clock {work.clock_port}, netlist clock {clocks[0]}")
            return rec
        # The RTL guess found no clock, but the netlist has one: synthesize again with it.
        work = flow.Design(design.design_id, design.top, design.files, clocks[0], design.source,
                           design.meta)
        flow.make_run_dir(run_dir, work)
        step2 = flow.run_step(run_dir, "synth", freq_mhz, timeout_s=synth_limit)
        log, net = _synth_result(run_dir, work)
        synth = synthcheck.classify(log, vlog_ok, net.exists())
        rec.update(synth_step=step2, synth=synth)
        rec["notes"].append(f"clock {clocks[0]} from the netlist, step 2 ran again")
        if not synth["synthesizes"]:
            rec["status"] = "does_not_synthesize"
            return rec
        net_text = net.read_text(errors="replace")
        clocks, resets = netlist.clocks_and_resets(net_text, work.top)
    rec["clock_port"] = work.clock_port
    summary = step2["summary"]
    rec.update(area_um2=summary.get("area_um2"), slack_ps=summary.get("slack_ps"),
               leaf_cells=summary.get("leaf_cells"))
    try:
        tb, how = _power_tb(work, net_text, work.clock_port, resets)
    except tbgen.TBError as exc:
        rec["status"] = "no_testbench"
        rec["notes"].append(str(exc))
        return rec
    rec.update(tb_power=tb.text, tb_module=tb.module, tb_dut_instance=tb.dut_instance, tb_how=how)
    flow.make_run_dir(run_dir, work, tb)
    step4 = flow.run_step(run_dir, "power", freq_mhz)
    rec.update(power_step=step4, total_power_w=step4["summary"].get("total_power_w"),
               annotation=flow.read_annotation(run_dir))
    if step4.get("killed"):
        rec["notes"].append(f"step 4 stopped: {step4['killed']}")
    if step4["exit_code"] != 0 or rec["total_power_w"] is None:
        rec["status"] = "power_failed"
    return rec


# ---------------------------------------------------------------- design

# The job "design" stops step 2 after 45 minutes (a very large MetRex memory can need hours). The
# design then gets a harness_error record, and build_dataset_v1 leaves it out.
DESIGN_SYNTH_TIMEOUT_S = 2700

def reach(period_ns, slack_ps):
    """The reachable clock frequency of a netlist: 1000 / (period - slack) MHz.

    This is the formula of MV's summary.sh, with the slack converted from ps to ns. (summary.sh
    subtracts the slack in ps from the period in ns, so for NanGate 15nm it prints no frequency.)
    Return (reachable period in ns, reachable frequency in MHz), or (None, None).
    """
    if period_ns is None or slack_ps is None:
        return None, None
    d = period_ns - slack_ps / 1000.0
    if d <= 0:
        return None, None
    return round(d, 5), round(1000.0 / d, 2)


def label_design(design, dry_run=False, freq_mhz=paths.DEFAULT_FREQ_MHZ):
    """All the answers of one design of the dataset, from one vlog run and one flow run.

    1. vlog -sv on the RTL (does it compile?)
    2. step 2 at freq_mhz (does it synthesize, and the reason if not; area; slack)
    3. if it synthesizes: the power testbench and step 4 (power)
    """
    run_dir = flow.make_run_dir(paths.RUNS_DIR / "design" / design.design_id, design)
    if dry_run:
        rec = design_record(design)
        rec.update(job="design", run_dir=str(run_dir), dry_run=True)
        return rec
    vlog_ok, vlog_error = vlog_check(run_dir)
    rec = label_ppa(design, freq_mhz, run_subdir="design", vlog_ok=vlog_ok)
    rec.update(job="design", vlog_ok=vlog_ok, vlog_error=vlog_error)
    period = (rec.get("synth_step") or {}).get("summary", {}).get("period_ns")
    rec["period_ns"] = period
    rec["reach_period_ns"], rec["reach_mhz"] = reach(period, rec.get("slack_ps"))
    return rec


# ---------------------------------------------------------------- period

def synth_at(run_dir, design, period_ns):
    """Run step 2 at one clock period, with its own results folder. Return (slack_ps, step)."""
    freq = 1000.0 / period_ns
    name = f"results_p{period_ns:.4f}".replace(".", "_")
    step = flow.run_step(run_dir, "synth", round(freq, 6), results_name=name)
    return step["summary"].get("slack_ps"), step


def find_tmin(design, rel_tol=0.02, max_runs=12, start_period_ns=2.0):
    """Find the minimum period T_min (ns) at which the worst slack is zero or positive.

    A bisection between a failing period and a passing period, to a resolution of rel_tol.
    Return a dict with T_min and every (period, slack) pair that DC gave.
    """
    run_dir = flow.make_run_dir(paths.RUNS_DIR / "period" / design.design_id, design)
    tried = []

    def run(p):
        slack, _step = synth_at(run_dir, design, p)
        tried.append({"period_ns": round(p, 4), "slack_ps": slack})
        return slack

    lo, hi = None, None          # lo fails, hi passes
    p = start_period_ns
    s = run(p)
    if s is None:
        return {"tmin_ns": None, "tried": tried, "status": "no_slack"}
    if s >= 0:
        hi = p
        p = max(0.01, (p - s / 1000.0) * 0.9)       # the critical path at p, less 10%
    else:
        lo = p
        p = (p - s / 1000.0) * 1.2
    while len(tried) < max_runs:
        s = run(p)
        if s is None:
            break
        if s >= 0:
            hi = p
        else:
            lo = p
        if lo is not None and hi is not None:
            if (hi - lo) / hi <= rel_tol:
                break
            p = (lo + hi) / 2.0
        elif hi is None:
            p = p * 1.5
        else:
            p = p * 0.7
    status = "ok" if (lo is not None and hi is not None and (hi - lo) / hi <= rel_tol) else "not_converged"
    return {"tmin_ns": round(hi, 4) if hi else None, "lo_fail_ns": round(lo, 4) if lo else None,
            "tried": tried, "status": status, "run_dir": str(run_dir)}


TIMING_FACTORS = (0.5, 0.8, 1.25, 2.0)


def label_period(design, dry_run=False, factors=TIMING_FACTORS):
    """timing_yesno: T_min of the design, then step 2 at factors x T_min.

    The correct answer of a question comes from the DC run at that period, not from the factor.
    """
    rec = design_record(design)
    rec.update(job="period", status="ok", clock_port=design.clock_port)
    if dry_run:
        rec["run_dir"] = str(flow.make_run_dir(paths.RUNS_DIR / "period" / design.design_id, design))
        rec["dry_run"] = True
        return rec
    search = find_tmin(design)
    rec.update(tmin=search, run_dir=search.get("run_dir"))
    if search["status"] != "ok" or not search["tmin_ns"]:
        rec["status"] = f"tmin_{search['status']}"
        return rec
    run_dir = Path(search["run_dir"])
    runs = []
    for f in factors:
        period = round(f * search["tmin_ns"], 4)
        slack, step = synth_at(run_dir, design, period)
        runs.append({"factor": f, "period_ns": period, "slack_ps": slack,
                     "results_dir": step["results_dir"]})
    rec["periods"] = runs
    return rec


# ---------------------------------------------------------------- driver

JOBS = {"synth": label_synth, "ppa": label_ppa, "period": label_period, "design": label_design}


def _log(*args):
    print(*args, flush=True)


def run_jobs(job, designs, limit=None, dry_run=False, log=_log, shard=None):
    """Run one job for a list of designs. Skip the designs that have a record already.

    shard (i, n) keeps only the designs at the positions p of the plan with p % n == i, so n
    processes can share one plan without overlap.
    """
    if shard:
        i, n = shard
        designs = [d for p, d in enumerate(designs) if p % n == i]
    done = done_ids(job)
    todo = [d for d in designs if d.design_id not in done]
    n_done = len(designs) - len(todo)
    if limit is not None:
        todo = todo[:limit]
    log(f"{job}: {len(designs)} designs in the plan, {n_done} of them done, {len(todo)} to run now"
        f"{' (dry run)' if dry_run else ''}")
    for i, design in enumerate(todo, 1):
        start = time.time()
        try:
            rec = JOBS[job](design, dry_run=dry_run)
        except flow.LicenseBusy as exc:
            log(f"stop: {exc}")
            return
        except (flow.FlowError, netlist.NetlistError) as exc:
            rec = design_record(design)
            rec.update(job=job, status="harness_error", notes=[f"{type(exc).__name__}: {exc}"])
        rec["harness_seconds"] = round(time.time() - start, 1)
        if dry_run:
            log(f"[{i}/{len(todo)}] {design.design_id}: run folder {rec.get('run_dir')}")
            continue
        append_record(job, rec)
        brief = {k: rec.get(k) for k in ("status", "area_um2", "slack_ps", "total_power_w")
                 if rec.get(k) is not None}
        syn = rec.get("synth") or {}
        if job == "synth":
            brief = {"synthesizes": syn.get("synthesizes"), "reason": syn.get("reason"),
                     "status": rec.get("status")}
        if job == "design":
            brief = {"compiles": rec.get("vlog_ok"), "synthesizes": syn.get("synthesizes"),
                     "reason": syn.get("reason"), "status": rec.get("status"),
                     "area_um2": rec.get("area_um2"), "slack_ps": rec.get("slack_ps"),
                     "reach_mhz": rec.get("reach_mhz"), "power_w": rec.get("total_power_w")}
        if job == "period":
            brief = {"status": rec["status"], "tmin_ns": (rec.get("tmin") or {}).get("tmin_ns"),
                     "slack_ps": [r["slack_ps"] for r in rec.get("periods", [])]}
        log(f"[{i}/{len(todo)}] {design.design_id}: {brief} ({rec['harness_seconds']} s)")
