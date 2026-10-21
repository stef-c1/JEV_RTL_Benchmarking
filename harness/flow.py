"""Make a run folder for one design, and run one step of MV's flow in it.

A run folder links to the scripts, the library, and the tool setup of MV's flow. It has its own
config.sh, rtl/, tb/, and results/. The config.sh is MV's config.sh with only the design lines
replaced (render_config). Thus each run uses MV's settings and MV's scripts without a change.
"""
import contextlib
import csv
import fcntl
import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import paths

SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")

STEP_SCRIPT = {"synth": "02_synth.sh", "power": "04_power.sh"}

# Text that shows that a tool got no license. The run is then not a result, so the step waits
# and runs again.
LICENSE_BUSY = [
    "(SEC-50)",                        # DC and PrimeTime: all licenses are in use
    "licenses are in use",
    "Unable to checkout a license",    # QuestaSim
    "Unable to checkout license",
]


class FlowError(Exception):
    """The harness cannot prepare or run a step. This is a harness error, not a design result."""


class LicenseBusy(FlowError):
    """No license was free after all retries."""


@dataclass
class Design:
    design_id: str            # unique name, also the name of the run folder
    top: str                  # the top module
    files: list               # [(file name, text)], the file of the top module last
    clock_port: str = ""      # "" for a design with no clock
    source: str = ""          # the dataset, for example "metrex"
    meta: dict = field(default_factory=dict)


@dataclass
class PowerTB:
    module: str               # the module name of the testbench, also its file name without .sv
    text: str                 # the exact file that the flow simulates
    dut_instance: str         # the instance name of the design in the testbench


def render_config(base_text, design, tb=None):
    """Return MV's config.sh with the design lines replaced.

    Only five lines change: DESIGN_NAME, CLOCK_PORT, RTL_FILES, TB_POWER, and DUT_INSTANCE. Each
    pattern must match exactly once, or the function stops with FlowError.
    """
    rtl_block = "RTL_FILES=(\n" + "".join(f'    "rtl/{name}"\n' for name, _ in design.files) + ")"
    tb_module = tb.module if tb else f"tb_power_{design.top}"
    dut = tb.dut_instance if tb else "dut"
    replacements = [
        (r'^DESIGN_NAME=".*"$', f'DESIGN_NAME="{design.top}"'),
        (r'^CLOCK_PORT=".*"$', f'CLOCK_PORT="{design.clock_port}"'),
        (r'^RTL_FILES=\(\n(?:[^\n]*\n)*?\)$', rtl_block),
        (r'^TB_POWER=".*"$', f'TB_POWER="{tb_module}"'),
        (r'^DUT_INSTANCE=".*"$', f'DUT_INSTANCE="{dut}"'),
    ]
    text = base_text
    for pattern, new in replacements:
        text, count = re.subn(pattern, lambda _m, new=new: new, text, flags=re.M)
        if count != 1:
            raise FlowError(f"config.sh: the pattern {pattern!r} matched {count} times, not once")
    return text


def make_run_dir(run_dir, design, tb=None):
    """Make (or update) the run folder of one design. Return its path."""
    run_dir = Path(run_dir)
    if not SAFE_NAME.match(run_dir.name):
        raise FlowError(f"unsafe run folder name: {run_dir.name}")
    if " " in str(run_dir):
        raise FlowError(f"the flow refuses a path with a space: {run_dir}")
    for name, _ in design.files:
        if not SAFE_NAME.match(name):
            raise FlowError(f"unsafe RTL file name: {name}")
    run_dir.mkdir(parents=True, exist_ok=True)
    for name in paths.FLOW_LINKS:
        link = run_dir / name
        if link.is_symlink():
            continue
        if link.exists():
            raise FlowError(f"{link} exists and is not a link to the flow")
        link.symlink_to(paths.FLOW_DIR / name)
    rtl_dir = run_dir / "rtl"
    rtl_dir.mkdir(exist_ok=True)
    for name, text in design.files:
        (rtl_dir / name).write_text(text)
    tb_dir = run_dir / "tb"
    tb_dir.mkdir(exist_ok=True)
    if tb is not None:
        if not SAFE_NAME.match(tb.module):
            raise FlowError(f"unsafe testbench name: {tb.module}")
        (tb_dir / f"{tb.module}.sv").write_text(tb.text)
    base = (paths.FLOW_DIR / "config.sh").read_text()
    (run_dir / "config.sh").write_text(render_config(base, design, tb))
    return run_dir


@contextlib.contextmanager
def tool_lock():
    """Hold one tool slot. With JEV_TOOL_SLOTS=1 (the default), only one tool runs at a time, also
    across harness processes. Slot 0 is the file .tool.lock, slot k the file .tool.lock.k."""
    paths.TOOL_LOCK.parent.mkdir(parents=True, exist_ok=True)
    slots = [paths.TOOL_LOCK] + [paths.TOOL_LOCK.with_name(f"{paths.TOOL_LOCK.name}.{k}")
                                 for k in range(1, max(1, paths.TOOL_SLOTS))]
    while True:
        for slot in slots:
            lock = open(slot, "w")
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                lock.close()
                continue
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
                lock.close()
            return
        time.sleep(2)


def _env(run_dir, freq_mhz, results_name):
    env = dict(os.environ)
    env["CLOCK_FREQ_MHZ"] = str(freq_mhz)
    env.pop("TECH", None)             # MV's default library (nangate15)
    if results_name == "results":
        env.pop("RESULTS_DIR", None)  # the flow default: <run folder>/results
    else:
        env["RESULTS_DIR"] = str(Path(run_dir) / results_name)
    return env


def run_step(run_dir, step, freq_mhz=paths.DEFAULT_FREQ_MHZ, results_name="results", retries=30,
             wait_s=60, timeout_s=4 * 3600):
    """Run one step of the flow ("synth" or "power") in a run folder.

    The step runs with stdin from /dev/null, so a tool that stops at a prompt gets an end of file
    and exits. If no license is free, the step waits wait_s seconds and runs again. Return a dict
    with the exit code, the time, the summary of summary.sh, and the log path.

    results_name is the results folder in the run folder. The flow default is "results". The
    timing test uses one results folder per clock period (the flow reads RESULTS_DIR).
    """
    run_dir = Path(run_dir)
    if step not in STEP_SCRIPT:
        raise FlowError(f"unknown step: {step}")
    out_log = run_dir / f"{step}_{results_name}.out"
    vcd_dir = run_dir / results_name / "4_power"
    for _attempt in range(retries):
        with tool_lock():
            start = time.time()
            killed = None
            with open(out_log, "w") as out:
                # A new session, so that a stop reaches the whole process group (bash, vsim, pt_shell).
                proc = subprocess.Popen(["bash", STEP_SCRIPT[step]], cwd=run_dir,
                                        env=_env(run_dir, freq_mhz, results_name),
                                        stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                                        start_new_session=True)
                limit_s = min(timeout_s, POWER_TIMEOUT_S) if step == "power" else timeout_s
                while proc.poll() is None:
                    time.sleep(2)
                    if time.time() - start > limit_s:
                        killed = f"time limit {limit_s} s"
                    elif step == "power" and _vcd_bytes(vcd_dir) > VCD_LIMIT_BYTES:
                        killed = f"VCD above {VCD_LIMIT_BYTES / 1e9:.1f} GB"
                    if killed:
                        _stop_group(proc)
                        break
            seconds = time.time() - start
        if killed and step != "power":
            raise FlowError(f"{step} stopped ({killed}): {run_dir}")
        text = out_log.read_text(errors="replace")
        if killed or not any(mark in text for mark in LICENSE_BUSY):
            break
        time.sleep(wait_s)
    else:
        raise LicenseBusy(f"no license after {retries} tries: {run_dir} {step}")
    vcd_deleted = None
    if step == "power":
        vcd_deleted = _delete_large_vcds(vcd_dir)
    return {
        "step": step,
        "freq_mhz": freq_mhz,
        "exit_code": proc.returncode if not killed else None,
        "killed": killed,
        "vcd_deleted": vcd_deleted,
        "seconds": round(seconds, 1),
        "results_dir": str(run_dir / results_name),
        "summary": read_summary(run_dir, freq_mhz, results_name),
        "out_log": str(out_log),
    }


# The guard of the power step (2026-10-13): the gate-level simulation of rev_lstm_v0 wrote a VCD of
# 8.85 GB in 5 minutes. Above these limits, the harness stops step 4. The design then keeps all
# its other answers, and only the power question drops.
POWER_TIMEOUT_S = 900
VCD_LIMIT_BYTES = 2 * 10**9
VCD_KEEP_BYTES = 200 * 10**6     # after step 4, a VCD above this size is deleted (the size is recorded)


def _vcd_bytes(folder):
    try:
        return sum(p.stat().st_size for p in Path(folder).glob("*.vcd"))
    except OSError:
        return 0


def _stop_group(proc):
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=15)
            return
        except subprocess.TimeoutExpired:
            continue


def _delete_large_vcds(folder):
    deleted = {}
    for p in Path(folder).glob("*.vcd"):
        try:
            size = p.stat().st_size
            if size > VCD_KEEP_BYTES:
                p.unlink()
                deleted[p.name] = size
        except OSError:
            continue
    return deleted or None


def _number(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def read_summary(run_dir, freq_mhz, results_name="results"):
    """Run MV's summary.sh (it starts no tool) and return its CSV row as a dict.

    The numbers are floats, and "n/a" becomes None.
    """
    run_dir = Path(run_dir)
    subprocess.run(["bash", "summary.sh"], cwd=run_dir, env=_env(run_dir, freq_mhz, results_name),
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    csv_path = run_dir / results_name / "summary.csv"
    if not csv_path.exists():
        return {}
    with open(csv_path) as f:
        row = next(csv.DictReader(f), {})
    out = dict(row)
    for key in ("freq_mhz", "period_ns", "area_um2", "slack_ps", "leaf_cells", "total_power_w"):
        if key in out:
            out[key] = _number(out[key])
    return out


ANNOTATION_RE = re.compile(r"Number of annotated nets = (\d+) \(([\d.]+)%\)")
TOTAL_NETS_RE = re.compile(r"Total number of nets = (\d+)")


def read_annotation(run_dir):
    """Return the VCD annotation of the power step from pt.log, or None.

    The flow writes results/4_power/activity_check.rpt, but in this PrimeTime release that file
    holds only "1". The numbers are in pt.log, after read_vcd.
    """
    log = Path(run_dir) / "results" / "4_power" / "pt.log"
    if not log.exists():
        return None
    text = log.read_text(errors="replace")
    m = ANNOTATION_RE.search(text)
    t = TOTAL_NETS_RE.search(text)
    if not m:
        return None
    return {"annotated_nets": int(m.group(1)), "annotated_pct": float(m.group(2)),
            "total_nets": int(t.group(1)) if t else None}
