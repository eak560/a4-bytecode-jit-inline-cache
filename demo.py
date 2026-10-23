"""
demo.py -- a paced, projector-friendly walkthrough of vm_ic_model.py

  python3 demo.py           step through, press Enter between beats
  python3 demo.py --fast    run straight through, no pauses
  python3 demo.py --beat 4  run one beat only

Keep this next to vm_ic_model.py. Beat 7 also runs v8_compare.js if Node is installed.
"""

import shutil
import subprocess
import sys
import time

import vm_ic_model as m

FAST = "--fast" in sys.argv
W = 70


def head(n, title):
    print("\n" + "-" * W)
    print(f"  BEAT {n}   {title}")
    print("-" * W)


def pause():
    if FAST:
        print()
        return
    try:
        input("        [Enter]")
    except EOFError:
        print()


def bar(value, scale, width=40):
    return "#" * max(1, int(round(value / scale * width)))


# ---------------------------------------------------------------- beat 1
def beat1():
    head(1, "The program we run")
    print("""
  Source (JavaScript-style):

      for (let i = 0; i < n; i++) {
          print(objects[i].x)          // <-- one property read, n times
      }

  Hand-compiled to our bytecode (a real engine has a parser here):
""")
    for pc, (op, arg) in enumerate(m.build_loop_program(5)):
        mark = "   <-- the call site we cache" if pc == m.GETFIELD_PC else ""
        print(f"      {pc:>2}  {op:<9}{'' if arg is None else arg}{mark}")
    print("""
  Without a cache, every GETFIELD scans the object's field names one by one
  until it finds "x". Our objects have 200 other fields, so that is slow.""")


# ---------------------------------------------------------------- beat 2
def beat2():
    head(2, "Correctness first: the baseline interpreter")
    vm = m.VM(objects=m.small_objects([3], 5))
    r = vm.run(m.build_loop_program(5))
    print(f"\n  Baseline run on 5 objects printed: {r['output']}")
    print(f"  Loop back-edge counter: {r['back_edge_counts']}  -> hot loop detected: {bool(r['hot_flags'])}")
    print("\n  Full test suite:")
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        tc = m.run_tests()
        ic = m.run_ic_tests()
    for name, status in tc + ic:
        print(f"      [{status}] {name}")
    print(f"\n  {sum(s == 'PASS' for _, s in tc + ic)} / {len(tc + ic)} passing."
          " The baseline is the reference every faster path is checked against.")


# ---------------------------------------------------------------- beat 3
def beat3():
    head(3, "The inline cache learning, one access at a time")
    print("\n  We feed one call site objects of new shapes and watch its state:\n")
    cache, stats = m.ICEntry(), m.new_stats()
    seq = m.small_objects([0], 1) * 2 + m.small_objects([1, 2], 2) + m.small_objects([0], 1) \
        + m.small_objects([3, 4, 5], 3)
    seen = []
    print(f"      {'access':<8}{'shape':<8}{'result':<8}state")
    for i, obj in enumerate(seq, 1):
        before = stats["hits"]
        m.ic_getprop(cache, obj, "x", stats)
        hit = stats["hits"] > before
        if obj.shape.id not in seen:
            seen.append(obj.shape.id)
        print(f"      {i:<8}{'S' + str(seen.index(obj.shape.id) + 1):<8}{'hit' if hit else 'MISS':<8}{cache.state}")
    print("""
  1 shape -> MONO (one comparison).  2-4 shapes -> POLY (short list).
  5+ shapes -> MEGA: a small shared table that has to keep evicting entries.""")


# ---------------------------------------------------------------- beat 4
def beat4():
    head(4, "Does it pay off? Baseline vs interpreter+IC")
    n = 30_000
    print(f"\n  {n:,} GETFIELD accesses per workload, same objects, same order.\n")
    rows = []
    for kind, label in [("mono", "Monomorphic (1 shape)"), ("poly", "Polymorphic (3 shapes)"),
                        ("mega", "Megamorphic (16 shapes)")]:
        rows.append((label, m.run_workload(kind, n, seed=42)))
    scale = max(max(r["t_base"], r["t_cached"]) for _, r in rows)
    for label, r in rows:
        print(f"  {label}   hit rate {r['hit_rate'] * 100:5.1f}%   wrong answers: {r['mismatches']}")
        print(f"      baseline {r['t_base']:.3f}s  {bar(r['t_base'], scale)}")
        print(f"      with IC  {r['t_cached']:.3f}s  {bar(r['t_cached'], scale)}   {r['speedup']:.2f}x\n")
    print("  Mono and poly get faster. Mega gets SLOWER: 16 shapes thrash a 4-slot")
    print("  table, so the bookkeeping costs more than it saves. Zero wrong answers.")


# ---------------------------------------------------------------- beat 5
def beat5():
    head(5, "Keeping the cache honest: a shape changes under it")
    objs = [m.make_object({"a": 1, "b": 2, "demo_x": 0}) for _ in range(3)]
    for o in objs:
        o.values[2] = 3
    shape = objs[0].shape
    cache, stats = m.ICEntry(), m.new_stats()
    m.ic_getprop(cache, objs[0], "demo_x", stats)
    _, ver, off = cache.entries[0]
    print(f"\n  Cache learned: demo_x is at slot {off} (shape version {ver})")
    m.mutate_shape(shape, 0, "new_field", objs)
    print(f"  Now a field is inserted at the front -> demo_x moves to slot {shape.props.index('demo_x')}, version {shape.version}")
    print(f"  A cache WITHOUT a version check would read slot {off}: {objs[0].values[off]}   (wrong)")
    v = m.ic_getprop(cache, objs[0], "demo_x", stats)
    print(f"  Our cache sees version {ver} != {shape.version}, treats it as a miss, re-learns: {v}   (right)")


# ---------------------------------------------------------------- beat 6
def beat6():
    head(6, "Tier 2: compile the hot path, bail out when a guess is wrong")
    a = [m.make_object({"a": 1, "x": 10}) for _ in range(50)]
    b = [m.make_object({"x": 20, "a": 1}) for _ in range(50)]
    objs = a + b
    prog = m.build_loop_program(len(objs))
    caches, stats = {}, m.new_stats()
    out = m.VM(objects=objs).run(prog, ic_mode=True, ic_caches=caches, stats=stats, tier2=True)["output"]
    base = m.VM(objects=objs).run(prog)["output"]
    print(f"""
  50 objects of shape A, then 50 of shape B.

  1. Loop goes hot while the site is MONO on A -> compile a direct load of slot 1,
     guarded by "is this still shape A?"
  2. Compiled path runs with no cache lookup at all ({stats['tier2_hits']} fast-path hits)
  3. Shape B arrives -> guard fails -> DEOPT: throw the code away,
     reset the cache to {stats['deopt_states'][0]}, redo the access the slow, safe way
  4. Site re-learns B and is compiled again (compiles total: {stats['compiles']})

  Deopts: {stats['deopts']}.  Output identical to baseline: {out == base}""")


# ---------------------------------------------------------------- beat 7
def beat7():
    head(7, "Same idea in a real engine: V8 (Node.js)")
    if not shutil.which("node"):
        print("\n  Node is not installed -- skip this beat.")
        return
    print("\n  Same experiment, real JavaScript, run by V8:\n", flush=True)
    subprocess.run(["node", "v8_compare.js"], cwd=sys.path[0] or ".")
    print("""
  Absolute times can't be compared (V8 is native, optimised C++; ours is a
  Python model). The point is the SHAPE of the result: V8 also slows down as
  a call site goes poly -> mega, for the same reason ours does.""")


BEATS = [beat1, beat2, beat3, beat4, beat5, beat6, beat7]

if __name__ == "__main__":
    if "--beat" in sys.argv:
        BEATS[int(sys.argv[sys.argv.index("--beat") + 1]) - 1]()
    else:
        for i, beat in enumerate(BEATS):
            beat()
            if i < len(BEATS) - 1:
                pause()
        print("\n" + "-" * W + "\n  End of demo.\n")
