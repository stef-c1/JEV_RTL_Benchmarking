"""Command line of the harness. Run it from the folder JEV_RTL with Python 3.12:

    python3.12 -m harness selftest
        Checks that need no tool run.

    python3.12 -m harness plan PLAN [--refresh]
        Show the designs of a plan, per source. Starts no tool. The first call freezes the plan in
        <work folder>/plans/PLAN.jsonl, with the full RTL of each design. Later calls, and the label
        command, read that file. --refresh makes the file again.

    python3.12 -m harness label JOB --plan PLAN [--limit N] [--only ID ...] [--dry-run]
        Run a label job (synth, ppa, or period) for the designs of a plan. --limit N runs only the next N
        designs that have no record yet. --only runs only the named designs. --dry-run makes the
        run folders and starts no tool.

    --shard I/N runs only the designs at plan positions p with p % N == I. Thus N processes can
    share one plan. With JEV_TOOL_SLOTS=N, up to N tools run at the same time (default 1).

    The environment variable JEV_WORK_DIR selects the work folder (default
    /volume1/users/scuycken/jev_rtl_work). All work folders share one tool lock.

    python3.12 -m harness build TEST|all
        Write data/questions/TEST.jsonl from the labels. Starts no tool.

    python3.12 -m harness reclassify
        Classify the synth records again from their logs (after a rule change). Starts no tool.

    python3.12 -m harness status [JOB]
        Count the records of each job per status.

Jobs: synth, ppa, period, design. Plans: see harness/plans.py.
"""
import argparse
import collections
import json
import sys

from . import build, labels, plans, selftest


def cmd_plan(args):
    designs = plans.get(args.plan, refresh=args.refresh)
    print(f"frozen plan file: {plans.frozen_path(args.plan)}")
    by_source = collections.Counter(d.source for d in designs)
    print(f"plan {args.plan}: {len(designs)} designs")
    for source, n in by_source.most_common():
        print(f"  {source:14s} {n}")
    if args.plan == "area_power":
        levels = collections.Counter(d.meta.get("sky130_level") for d in designs if d.source == "metrex")
        print("  MetRex per Sky130 level (estimate):", dict(sorted(levels.items())))
    if args.plan == "revolution_pairs":
        keys = collections.Counter(d.meta["key"] for d in designs)
        print("  per REvolution design:", dict(keys.most_common()))
    for d in designs[:args.show]:
        print(f"  {d.design_id}  top={d.top}  clock={d.clock_port or '-'}  files={len(d.files)}")


def cmd_label(args):
    designs = plans.get(args.plan)
    if args.only:
        designs = [d for d in designs if d.design_id in set(args.only)]
    shard = tuple(int(x) for x in args.shard.split("/")) if args.shard else None
    labels.run_jobs(args.job, designs, limit=args.limit, dry_run=args.dry_run, shard=shard)


def cmd_build(args):
    tests = [args.test] if args.test != "all" else list(build.BUILDERS)
    for test in tests:
        records, stats = build.BUILDERS[test]()
        out = build.write_questions(test, records)
        over = sum(1 for r in records if r.get("over_token_limit"))
        print(f"{test}: {len(records)} records -> {out} ({over} above the token limit) {stats}")
        if test == "dataset_v1" and records:
            card = out.with_suffix(".card.md")
            card.write_text(build.datacard(records, stats))
            print(f"data card: {card}")


def cmd_reclassify(args):
    n, changed = labels.reclassify_synth()
    print(f"synth: {n} records, {changed} with a new result")


def cmd_status(args):
    jobs = [args.job] if args.job else list(labels.JOBS)
    for job in jobs:
        path = labels.label_file(job)
        if not path.exists():
            print(f"{job}: no records")
            continue
        counts = collections.Counter()
        for line in open(path):
            r = json.loads(line)
            if job == "design":
                syn = r.get("synth") or {}
                key = ("compiles" if r.get("vlog_ok") else "no compile") + ", " + (
                    "synthesizes" if syn.get("synthesizes") else f"no synth: {syn.get('reason')}")
                counts[f"{key} [{r.get('status')}]"] += 1
            elif job == "synth" and "synth" in r:
                counts["synthesizes" if r["synth"]["synthesizes"] else f"no: {r['synth']['reason']}"] += 1
            else:
                counts[r.get("status")] += 1
        print(f"{job}: {sum(counts.values())} records {dict(counts.most_common())}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python3.12 -m harness", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    p = sub.add_parser("plan")
    p.add_argument("plan", choices=sorted(plans.PLANS))
    p.add_argument("--show", type=int, default=5)
    p.add_argument("--refresh", action="store_true", help="make the frozen plan file again")
    p = sub.add_parser("label")
    p.add_argument("job", choices=sorted(labels.JOBS))
    p.add_argument("--plan", required=True, choices=sorted(plans.PLANS))
    p.add_argument("--limit", type=int)
    p.add_argument("--only", nargs="+", help="run only these design ids of the plan")
    p.add_argument("--shard", help="I/N: run only the designs at plan positions p with p %% N == I")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("build")
    p.add_argument("test", choices=sorted(build.BUILDERS) + ["all"])
    sub.add_parser("reclassify")
    p = sub.add_parser("status")
    p.add_argument("job", nargs="?", choices=sorted(labels.JOBS))
    args = parser.parse_args(argv)
    if args.cmd == "selftest":
        return 0 if selftest.run_all() else 1
    {"plan": cmd_plan, "label": cmd_label, "build": cmd_build, "reclassify": cmd_reclassify,
     "status": cmd_status}[args.cmd](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
