# A4: Bytecode JIT Compiler with Inline Caching

BCSE307 Compiler Design project (VIT). A Python reference model of a stack-based bytecode VM with an inline cache (UNINIT → MONO → POLY → MEGA), shape versioning, and a tier-2 guarded fast path with deoptimisation, plus a small JavaScript front end checked against Node.

Pure Python 3 standard library; Node.js is only needed for the comparison against V8.

## Run

```bash
python3 vm_ic_model.py              # 17 tests (TC1–TC12, IC1–IC5) + mono/poly/mega benchmark
python3 run_js.py examples/*.js     # compile JS -> our bytecode, run 3 ways, compare with Node
python3 demo.py                     # paced presentation walkthrough (--fast, --beat N)
node v8_compare.js                  # the same mono/poly/mega experiment inside V8
```

## Files

| File | What it is |
|---|---|
| `vm_ic_model.py` | VM, inline cache, tier 2 + deopt, tests and benchmarks |
| `jsc.py` | Compiler from a JavaScript subset to the VM's bytecode |
| `run_js.py` | Runs a `.js` file in Node and on our VM (baseline / + IC / + IC + tier 2) and compares output |
| `examples/` | Test programs: language features, mono / poly / mega / wide objects, deopt |
| `demo.py`, `v8_compare.js` | Live demo scripts |
| `A4_Review2_*` | Review 2 report, slides and presentation script (`_Updated` = 23-slide version with the JS front end) |
| `CLAUDE.md` | Notes on the architecture for Claude Code |
