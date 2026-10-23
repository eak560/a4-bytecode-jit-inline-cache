"""
threshold_sweep.py -- effect of the hot-loop threshold on tier-2 compilation
=============================================================================
The VM marks a loop hot after `hot_threshold` back-edges; only then can a
monomorphic GETFIELD site be compiled to a guarded tier-2 fast path. This sweeps
the threshold on two workloads and reports compiles, fast-path reads, deopts
and output mismatches against the baseline interpreter. Every number is measured.

  python3 threshold_sweep.py
"""

import vm_ic_model as m

THRESHOLDS = [1, 2, 5, 10, 25, 50, 100]


def run(objs, threshold):
    prog = m.build_loop_program(len(objs))
    base = m.VM(objects=objs).run(prog)["output"]
    stats = m.new_stats()
    out = m.VM(objects=objs, hot_threshold=threshold).run(
        prog, ic_mode=True, ic_caches={}, stats=stats, tier2=True)["output"]
    mism = sum(1 for a, b in zip(base, out) if a != b) + abs(len(base) - len(out))
    return stats, mism


def main():
    shape_a = [m.make_object({"a": 1, "x": 10}) for _ in range(50)]
    shape_b = [m.make_object({"x": 20, "a": 1}) for _ in range(50)]
    mono = [m.make_object({"a": 1, "x": 10}) for _ in range(200)]
    for title, objs in [("IC5 workload: 50 shape-A then 50 shape-B objects", shape_a + shape_b),
                        ("Monomorphic workload: 200 objects of one shape", mono)]:
        print(title)
        print(f"  {'threshold':>9}{'compiles':>10}{'fast-path reads':>17}{'deopts':>8}{'mismatches':>12}")
        for t in THRESHOLDS:
            s, mism = run(objs, t)
            print(f"  {t:>9}{s['compiles']:>10}{s['tier2_hits']:>17}{s['deopts']:>8}{mism:>12}")
        print()


if __name__ == "__main__":
    main()
