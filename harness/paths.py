"""Fixed paths and constants of the harness."""
import os
from pathlib import Path

# The project folder JEV_RTL (the parent of this package).
PROJECT_DIR = Path(__file__).resolve().parent.parent

# MV's flow. The harness reads it and links to it, but never writes into it.
FLOW_DIR = PROJECT_DIR / "flow" / "RTL_flow_Nangate15"

# The local disk of mercury with no quota. Run folders, logs, and labels go here.
# The environment variable JEV_WORK_DIR selects another work folder, for example for the validation
# runs. The tool lock (below) stays the same for all work folders.
VOLUME_DIR = Path("/volume1/users/scuycken")
WORK_DIR = Path(os.environ.get("JEV_WORK_DIR", str(VOLUME_DIR / "jev_rtl_work")))
RUNS_DIR = WORK_DIR / "runs"
LABELS_DIR = WORK_DIR / "labels"

# The public datasets, downloaded on 2026-10-09.
DATA_DIR = VOLUME_DIR / "jev_rtl_data"
VERILOGEVAL_DIR = DATA_DIR / "verilog-eval" / "dataset_spec-to-rtl"
RTLLM_DIR = DATA_DIR / "rtllm"
METREX_FILE = DATA_DIR / "metrex.json"

# MV's earlier agent runs.
REVOLUTION_DIR = Path("/users/micas/scuycken/Claude/RTL_LLM_Loop_REvolution")
ORCHESTRATOR_DIRS = [
    Path("/users/micas/scuycken/workspace/Orchestrator_exp_20261007"),
    Path("/users/micas/scuycken/workspace/Orchestrator_exp_20261008"),
]

# The question files that the builders write. They stay in the project. With JEV_WORK_DIR set
# (for example for the validation runs), they go to <work folder>/questions.
QUESTIONS_DIR = (WORK_DIR / "questions") if "JEV_WORK_DIR" in os.environ else (PROJECT_DIR / "data" / "questions")

# The tool lock. Each tool run holds it, so only one tool runs at a time, also across several
# harness processes. The DC licenses are shared with other users.
TOOL_LOCK = VOLUME_DIR / "jev_rtl_work" / ".tool.lock"
# The number of tools that may run at the same time (default 1). Each slot is one lock file.
TOOL_SLOTS = int(os.environ.get("JEV_TOOL_SLOTS", "1"))

# The files and folders of the flow that a run folder links to. A run folder writes its own
# config.sh, rtl/, tb/, and results/.
FLOW_LINKS = [
    "00_check.sh", "01_verify.sh", "02_synth.sh", "03_verify_syn.sh", "04_power.sh",
    "common.sh", "summary.sh", "clean.sh", "run_all.sh", "scripts", "tech", "tools",
]

# 1 gate equivalent (GE) is the area of NAND2_X1 in the NanGate 15nm library (um2).
GE_UM2 = 0.196608

# The default clock of the flow (config.sh: CLOCK_FREQ_MHZ default 500).
DEFAULT_FREQ_MHZ = 500
