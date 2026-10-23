"""
run_js.py -- run a JavaScript file through BOTH Node (V8) and our engine
==========================================================================
  python3 run_js.py examples/points_mono.js
  python3 run_js.py examples/*.js              several files + summary table
  python3 run_js.py FILE --bytecode            also print the compiled bytecode
  python3 run_js.py FILE --max-steps 100000    lower the VM step limit (catches infinite loops fast)

For each file:
  1. Node runs it            -> the reference output (what real JavaScript says)
  2. jsc.py compiles it      -> our bytecode
  3. our VM runs it 3 ways   -> baseline, + inline cache, + inline cache + tier 2
Every one of our outputs must match Node's line for line. Times are only
compared between our own three modes (V8 is native code; ours is a Python model).
"""

import shutil
import subprocess
import sys
import time

import vm_ic_model as m
from jsc import CompileError, compile_js

MAX_STEPS = 200_000_000


def node_output(path):
    if not shutil.which("node"):
        return None
    try:
        r = subprocess.run(["node", path], capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        return ["NODE TIMEOUT: did not finish in 10 s"]
    if r.returncode != 0:
        # e.g. a ReferenceError: keep Node's first error line as its "output"
        err = next((l for l in r.stderr.splitlines() if "Error" in l), "error")
        return [f"NODE ERROR: {err.strip()}"]
    return r.stdout.splitlines()


def run_mode(code, comp, ic, tier2):
    vm = m.VM(n_locals=max(1, len(comp.slots)), objects=comp.objects)
    caches, stats = {}, m.new_stats()
    t0 = time.perf_counter()
    try:
        r = vm.run(code, ic_mode=ic, ic_caches=caches, stats=stats, max_steps=MAX_STEPS, tier2=tier2)
        out = [str(v) for v in r["output"]]
    except (m.VMError, IndexError, AttributeError) as e:
        # report the runtime failure as output so it shows up in the Node comparison
        out = [f"RUNTIME ERROR: {e}"]
    dt = time.perf_counter() - t0
    return out, dt, caches, stats


def first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return f"line {i + 1}: expected {x}, got {y}"
    return f"expected {len(a)} lines, got {len(b)}"


def run_file(path, show_bytecode):
    print("=" * 72)
    print(f"  {path}")
    print("=" * 72)
    src = open(path).read()
    try:
        code, comp = compile_js(src)
    except CompileError as e:
        print(f"  COMPILE ERROR: {e}\n")
        return {"file": path, "ok": False}

    shapes = {o.shape.id for o in comp.objects if isinstance(o, m.Obj)}
    n_vars = sum(1 for k in comp.slots if not k.startswith("$"))
    print(f"  compiled: {len(src.splitlines())} JS lines -> {len(code)} bytecode instructions, "
          f"{n_vars} variables, {len(comp.objects)} objects in {len(shapes)} shape(s), "
          f"{len(comp.sites)} property-read sites")
    if show_bytecode:
        for pc, (op, arg) in enumerate(code):
            print(f"      {pc:>4}  {op:<9}{'' if arg is None else arg}")

    ref = node_output(path)
    modes = [("our VM: baseline", False, False),
             ("our VM: + inline cache", True, False),
             ("our VM: + inline cache + tier 2", True, True)]
    results = [run_mode(code, comp, ic, t2) for _, ic, t2 in modes]
    base_out, base_t = results[0][0], results[0][1]

    if ref is None:
        print("  (node not installed -- checking our three modes against each other only)")
        ref = base_out
    print(f"  output: {', '.join(ref[:6])}{' ...' if len(ref) > 6 else ''}\n")
    print(f"  {'':<34}{'matches Node?':<16}{'time':>8}{'vs baseline':>13}")
    ok = True
    for (label, _, _), (out, dt, _, _) in zip(modes, results):
        same = out == ref
        ok &= same
        verdict = "yes" if same else "NO -- " + first_diff(ref, out)
        print(f"  {label:<34}{verdict:<16}{dt:>7.3f}s{base_t / dt:>12.2f}x")

    _, _, caches, stats = results[1]
    total = stats["hits"] + stats["misses"]
    if comp.sites:
        print("\n  property-read call sites (inline-cache state at end of run):")
        for pc, (line, prop) in sorted(comp.sites.items()):
            c = caches.get(pc)
            state = c.state if c else "never run"
            n = len(c.entries) if c and c.state != "MEGA" else (len(c.mega_table) if c else 0)
            text = comp.src_lines[line - 1].strip()
            print(f"    line {line:<3} .{prop:<6} {state:<7} {n} shape(s) cached   | {text[:40]}")
        print(f"  cache hits: {stats['hits']:,} / {total:,}  ({stats['hits'] / total * 100:.1f}%)")
        s2 = results[2][3]
        print(f"  tier 2: {s2['compiles']} compile(s), {s2['tier2_hits']:,} fast-path reads, "
              f"{s2['deopts']} deopt(s)")
    print()
    return {"file": path, "ok": ok, "base": base_t, "ic": results[1][1], "t2": results[2][1],
            "hit": stats["hits"] / total if total else None, "deopts": results[2][3]["deopts"]}


def main():
    global MAX_STEPS
    argv = sys.argv[1:]
    if "--max-steps" in argv:
        i = argv.index("--max-steps")
        MAX_STEPS = int(argv[i + 1])
        del argv[i:i + 2]
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        sys.exit(1)
    rows = [run_file(p, "--bytecode" in sys.argv) for p in args]
    if len(rows) > 1:
        print("=" * 72)
        print("  SUMMARY")
        print("=" * 72)
        print(f"  {'file':<28}{'= Node':<8}{'hit rate':>9}{'IC':>8}{'IC+T2':>8}{'deopts':>8}")
        for r in rows:
            if "base" not in r:
                print(f"  {r['file']:<28}{'ERROR':<8}")
                continue
            hit = f"{r['hit'] * 100:.1f}%" if r["hit"] is not None else "-"
            print(f"  {r['file']:<28}{'yes' if r['ok'] else 'NO':<8}{hit:>9}"
                  f"{r['base'] / r['ic']:>7.2f}x{r['base'] / r['t2']:>7.2f}x{r['deopts']:>8}")
        print("\n  IC / IC+T2 = speedup over our own baseline interpreter on the same program.")
    sys.exit(0 if all(r["ok"] for r in rows) else 1)


if __name__ == "__main__":
    main()
