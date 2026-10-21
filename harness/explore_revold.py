"""Analysis of the old REvolution sample (plans revold_pairs_sample and revold_failed_sample).

Run with JEV_WORK_DIR set to the work folder of the sample:
    JEV_WORK_DIR=/volume1/users/scuycken/jev_rtl_work/explore_revold python3.12 -m harness.explore_revold

It starts no tool. It prints, per problem: the status of each candidate in MV's flow, the area and
the power at 500 MHz (NanGate 15nm) next to the REvolution values (NanGate 45nm), the number of
pairs that differ by 10% or more, and whether all candidates got the same testbench.
"""
import itertools
import json
from collections import Counter, defaultdict

from . import labels, paths


def _rank_agreement(xs, ys):
    """The fraction of pairs that have the same order in xs and in ys (ties do not count)."""
    same = total = 0
    for (a, b), (c, d) in zip(itertools.combinations(xs, 2), itertools.combinations(ys, 2)):
        if a == b or c == d:
            continue
        total += 1
        same += (a < b) == (c < d)
    return same, total


def main():
    ppa = [json.loads(l) for l in open(labels.label_file("ppa"))] if labels.label_file("ppa").exists() else []
    syn = [json.loads(l) for l in open(labels.label_file("synth"))] if labels.label_file("synth").exists() else []
    print(f"ppa records: {len(ppa)}  {dict(Counter(r.get('status') for r in ppa))}")
    groups = defaultdict(list)
    for r in ppa:
        groups[r["meta"]["problem"]].append(r)
    tot_pairs = Counter()
    agree = Counter()
    for problem, rows in sorted(groups.items()):
        ok = [r for r in rows if r.get("status") == "ok" and (r.get("slack_ps") or -1) >= 0
              and (r.get("annotation") or {}).get("annotated_pct", 0) >= 95]
        print(f"\n{problem}: {len(rows)} candidates, {len(ok)} usable "
              f"(status {dict(Counter(r.get('status') for r in rows))})")
        for r in sorted(rows, key=lambda r: (r["meta"]["ppa_ng45"] or {}).get("area") or 0):
            ng45 = r["meta"]["ppa_ng45"] or {}
            ann = (r.get("annotation") or {}).get("annotated_pct")
            print(f"   {r['design_id'][-12:]}  NG45 area {ng45.get('area')!s:>9} power {ng45.get('power')!s:>11}"
                  f"  |  NG15 area {r.get('area_um2')!s:>10} um2  power {r.get('total_power_w')!s:>10} W"
                  f"  slack {r.get('slack_ps')!s:>8}  annot {ann!s:>5}  {r.get('status')}")
        tbs = {r.get("tb_power") for r in ok}
        print(f"   same testbench for all usable candidates: {len(tbs) <= 1}")
        for field, ng45_key in (("area_um2", "area"), ("total_power_w", "power")):
            vals = [r[field] for r in ok]
            n10 = sum(1 for a, b in itertools.combinations(vals, 2) if min(a, b) > 0 and max(a, b) / min(a, b) >= 1.1)
            tot_pairs[field] += n10
            tot_pairs[field + "_all"] += len(vals) * (len(vals) - 1) // 2
            s, t = _rank_agreement([r["meta"]["ppa_ng45"][ng45_key] for r in ok], vals)
            agree[field] += s
            agree[field + "_total"] += t
            print(f"   {field}: {n10} of {len(vals) * (len(vals) - 1) // 2} pairs differ by 10% or more; "
                  f"the order of NG45 and NG15 agrees in {s} of {t} pairs")
    print("\nTotal:")
    for field in ("area_um2", "total_power_w"):
        print(f"   {field}: {tot_pairs[field]} of {tot_pairs[field + '_all']} pairs differ by 10% or more; "
              f"NG45 and NG15 order agree in {agree[field]} of {agree[field + '_total']} pairs")
    if syn:
        print(f"\nsynth records (candidates that failed in REvolution): {len(syn)}")
        print("   ", dict(Counter("synthesizes" if r["synth"]["synthesizes"] else f"no: {r['synth']['reason']}"
                                 for r in syn)))
        for r in syn:
            s = r["synth"]
            if not s["synthesizes"]:
                print(f"   {r['design_id']}: {s['reason']} errors {s['errors'][:6]} vlog_ok={r.get('vlog_ok')}")


if __name__ == "__main__":
    main()
