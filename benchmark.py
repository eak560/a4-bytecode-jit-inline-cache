"""
benchmark.py -- repeatable benchmark run for the final report
==============================================================
Runs every timing experiment REPS times and reports the median, so a single
noisy run cannot distort the result. Hit rates and mismatch counts are
deterministic (fixed seeds) and are reported once.

  python3 benchmark.py            # 5 repetitions (about 2 minutes)
  python3 benchmark.py --reps 3
  python3 benchmark.py --json results.json

Sections: (A) 100,000-access synthetic workloads, (B) megamorphic capacity and
policy sweep, (C) the JavaScript examples in three modes, (D) the same
mono/poly/mega experiment in V8 (needs Node).
"""

import json
import os
import shutil
import statistics
import subprocess
import sys
import time

import vm_ic_model as m
from jsc import compile_js

HERE = os.path.dirname(os.path.abspath(__file__))
REPS = int(sys.argv[sys.argv.index("--reps") + 1]) if "--reps" in sys.argv else 5
med = statistics.median


def section_a():
    rows = []
    for kind in ("mono", "poly", "mega"):
        runs = [m.run_workload(kind, 100_000, seed=42) for _ in range(REPS)]
        rows.append({"workload": kind, "hit_rate": runs[0]["hit_rate"],
                     "hits": runs[0]["hits"], "misses": runs[0]["misses"],
                     "t_base": med(r["t_base"] for r in runs), "t_ic": med(r["t_cached"] for r in runs),
                     "speedup": med(r["speedup"] for r in runs),
                     "mismatches": sum(r["mismatches"] for r in runs)})
    return rows


def section_b():
    rows = []
    for cap in (4, 8, 16):
        for policy in ("FIFO", "LRU"):
            m.MEGA_CACHE_CAPACITY, m.MEGA_POLICY = cap, policy
            runs = [m.run_workload("mega", 100_000, seed=42) for _ in range(REPS)]
            rows.append({"capacity": cap, "policy": policy, "hit_rate": runs[0]["hit_rate"],
                         "speedup": med(r["speedup"] for r in runs),
                         "mismatches": sum(r["mismatches"] for r in runs)})
    m.MEGA_CACHE_CAPACITY, m.MEGA_POLICY = 4, "FIFO"
    return rows


def time_mode(code, comp, ic, t2):
    vm = m.VM(n_locals=max(1, len(comp.slots)), objects=comp.objects)
    stats = m.new_stats()
    t0 = time.perf_counter()
    vm.run(code, ic_mode=ic, ic_caches={}, stats=stats, max_steps=200_000_000, tier2=t2)
    return time.perf_counter() - t0, stats


def section_c():
    rows = []
    for name in ("points_mono.js", "points_poly.js", "points_mega.js", "points_wide.js"):
        code, comp = compile_js(open(os.path.join(HERE, "examples", name)).read())
        base = [time_mode(code, comp, False, False)[0] for _ in range(REPS)]
        ic = [time_mode(code, comp, True, False) for _ in range(REPS)]
        t2 = [time_mode(code, comp, True, True) for _ in range(REPS)]
        s = ic[0][1]
        total = s["hits"] + s["misses"]
        rows.append({"program": name, "hit_rate": s["hits"] / total if total else 0.0,
                     "t_base": med(base), "t_ic": med(t for t, _ in ic), "t_t2": med(t for t, _ in t2),
                     "ic_speedup": med(base) / med(t for t, _ in ic),
                     "t2_speedup": med(base) / med(t for t, _ in t2),
                     "fast_path_reads": t2[0][1]["tier2_hits"]})
    return rows


def section_d():
    if not shutil.which("node"):
        return None
    ratios = {"poly": [], "mega": []}
    for _ in range(3):
        out = subprocess.run(["node", os.path.join(HERE, "v8_compare.js")], capture_output=True, text=True).stdout
        for line in out.splitlines():
            if line.startswith("Polymorphic"):
                ratios["poly"].append(float(line.split("ms")[1].split("x")[0]))
            if line.startswith("Megamorphic"):
                ratios["mega"].append(float(line.split("ms")[1].split("x")[0]))
    return {"poly_vs_mono": med(ratios["poly"]), "mega_vs_mono": med(ratios["mega"])}


def main():
    t0 = time.time()
    res = {"reps": REPS, "A": section_a(), "B": section_b(), "C": section_c(), "D": section_d()}
    print(f"Median of {REPS} runs (Python {sys.version.split()[0]})\n")
    print("A. Synthetic workloads, 100,000 GETFIELD accesses")
    for r in res["A"]:
        print(f"   {r['workload']:<5} hit {r['hit_rate'] * 100:5.1f}%  base {r['t_base']:.3f}s  IC {r['t_ic']:.3f}s  "
              f"{r['speedup']:.2f}x  mismatches {r['mismatches']}")
    print("\nB. Megamorphic capacity x policy (16 shapes)")
    for r in res["B"]:
        print(f"   {r['capacity']:>2} slots {r['policy']:<4} hit {r['hit_rate'] * 100:5.1f}%  {r['speedup']:.2f}x  "
              f"mismatches {r['mismatches']}")
    print("\nC. JavaScript examples (speedup over baseline)")
    for r in res["C"]:
        print(f"   {r['program']:<16} hit {r['hit_rate'] * 100:5.1f}%  IC {r['ic_speedup']:.2f}x  "
              f"IC+T2 {r['t2_speedup']:.2f}x  fast-path reads {r['fast_path_reads']:,}")
    if res["D"]:
        print(f"\nD. V8: poly {res['D']['poly_vs_mono']:.2f}x and mega {res['D']['mega_vs_mono']:.2f}x the mono time")
    print(f"\n({time.time() - t0:.0f} s)")
    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w") as f:
            json.dump(res, f, indent=2)


if __name__ == "__main__":
    main()
