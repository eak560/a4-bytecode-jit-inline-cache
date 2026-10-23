"""
mega_tuning.py -- tune the megamorphic (MEGA) inline cache
===========================================================
The Review 2 benchmark found the MEGA cache (4 slots, FIFO eviction) hits only
~25% on a 16-shape workload and is slower than no cache at all (0.89x). This
sweeps the two knobs -- table capacity and eviction policy -- on the same
100,000-access, 16-shape workload (seed 42) and reports hit rate and speedup
over the baseline interpreter. Every number is measured on this run.

    python3 mega_tuning.py
"""

import vm_ic_model as m

N = 100_000
CONFIGS = [(4, "FIFO"), (4, "LRU"), (8, "FIFO"), (8, "LRU"), (16, "FIFO"), (16, "LRU")]


def main():
    print(f"Megamorphic workload: 16 shapes, n={N:,} accesses, seed 42\n")
    print(f"  {'capacity':>8}  {'policy':<6}{'hit rate':>10}{'baseline':>11}{'with IC':>10}{'speedup':>9}  mismatches")
    rows = []
    for cap, policy in CONFIGS:
        m.MEGA_CACHE_CAPACITY, m.MEGA_POLICY = cap, policy
        r = m.run_workload("mega", N, seed=42)
        rows.append((cap, policy, r))
        print(f"  {cap:>8}  {policy:<6}{r['hit_rate'] * 100:>9.1f}%{r['t_base']:>10.3f}s{r['t_cached']:>9.3f}s"
              f"{r['speedup']:>8.2f}x  {r['mismatches']}")
    m.MEGA_CACHE_CAPACITY, m.MEGA_POLICY = 4, "FIFO"   # restore defaults
    best = max(rows, key=lambda x: x[2]["speedup"])
    print(f"\nBest: capacity {best[0]}, {best[1]} -> {best[2]['hit_rate'] * 100:.1f}% hits, "
          f"{best[2]['speedup']:.2f}x vs baseline")


if __name__ == "__main__":
    main()
