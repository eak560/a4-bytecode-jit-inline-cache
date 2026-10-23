"""
test_all.py -- the complete A4 regression suite in one command
================================================================
  python3 test_all.py
  python3 test_all.py --json results.json     also save every check as JSON

Runs, in order:
  1. Unit tests      TC1-TC12 (VM) and IC1-IC5 (inline cache, invalidation, deopt)
  2. End-to-end      every examples/*.js: compile, run in 3 modes, compare with Node
  3. Invalid input   every tests/invalid/*.js must fail with the expected diagnostic
  4. Stress          50,000-access mono / poly / mega workloads, 0 mismatches each
Exit status is 0 only if every check passes.
"""

import contextlib
import glob
import io
import os
import shutil
import subprocess
import sys
import json

import vm_ic_model as m
from jsc import CompileError, compile_js

HERE = os.path.dirname(os.path.abspath(__file__))
rows = []   # (group, name, expected, actual, passed)


def record(group, name, expected, actual, passed):
    rows.append((group, name, expected, actual, passed))


# ---------------- 1. unit tests ----------------
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    unit = m.run_tests() + m.run_ic_tests()
for name, status in unit:
    record("unit", name.split(" ")[0], "PASS", status, status == "PASS")


# ---------------- 2. end-to-end against Node ----------------
def run_vm(code, comp, ic, tier2, max_steps=200_000_000):
    vm = m.VM(n_locals=max(1, len(comp.slots)), objects=comp.objects)
    r = vm.run(code, ic_mode=ic, ic_caches={}, stats=m.new_stats(), max_steps=max_steps, tier2=tier2)
    return [str(v) for v in r["output"]]


have_node = shutil.which("node") is not None
for path in sorted(glob.glob(os.path.join(HERE, "examples", "*.js"))):
    name = os.path.basename(path)
    code, comp = compile_js(open(path).read())
    outs = [run_vm(code, comp, ic, t2) for ic, t2 in ((False, False), (True, False), (True, True))]
    if have_node:
        ref = subprocess.run(["node", path], capture_output=True, text=True, timeout=60).stdout.splitlines()
    else:
        ref = outs[0]
    ok = all(o == ref for o in outs)
    record("end-to-end", name, f"{len(ref)} lines = Node", "all 3 modes match" if ok else "MISMATCH", ok)


# ---------------- 3. invalid / failure inputs ----------------
EXPECTED = {
    "syntax_error.js": ("compile", "expected ')'"),
    "undefined_variable.js": ("compile", "'y' is not defined"),
    "unsupported_string.js": ("compile", "unexpected character"),
    "unsupported_function.js": ("compile", "'function' is not supported"),
    "division_by_zero.js": ("runtime", "division by zero"),
    "infinite_loop.js": ("runtime", "step limit exceeded"),
    "missing_property.js": ("runtime", "property 'y' not found"),
}
for path in sorted(glob.glob(os.path.join(HERE, "tests", "invalid", "*.js"))):
    name = os.path.basename(path)
    stage, needle = EXPECTED[name]
    try:
        code, comp = compile_js(open(path).read())
        try:
            run_vm(code, comp, True, True, max_steps=100_000)
            actual, ok = "ran without error", False
        except (m.VMError, AttributeError, IndexError) as e:
            msg = str(e)
            actual = f"runtime error: {msg}"
            ok = stage == "runtime" and needle in msg
    except CompileError as e:
        actual = f"compile error: {e}"
        ok = stage == "compile" and needle in str(e)
    record("invalid", name, f"{stage} error ({needle})", actual, ok)


# ---------------- 4. stress ----------------
for kind in ("mono", "poly", "mega"):
    r = m.run_workload(kind, 50_000, seed=7)
    record("stress", f"{kind} 50,000 reads", "0 mismatches", f"{r['mismatches']} mismatches", r["mismatches"] == 0)


# ---------------- report ----------------
print(f"{'group':<11} {'test':<26} {'expected':<34} {'actual':<44} result")
print("-" * 125)
for g, n, e, a, p in rows:
    print(f"{g:<11} {n:<26} {e[:34]:<34} {a[:44]:<44} {'PASS' if p else 'FAIL'}")
passed = sum(1 for r in rows if r[4])
print("-" * 125)
print(f"{passed} / {len(rows)} checks passed" + ("" if have_node else "  (Node not found: end-to-end compared modes with each other)"))
if "--json" in sys.argv:
    with open(sys.argv[sys.argv.index("--json") + 1], "w") as f:
        json.dump([dict(zip(("group", "name", "expected", "actual", "passed"), r)) for r in rows], f, indent=1)
raise SystemExit(0 if passed == len(rows) else 1)
