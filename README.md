# A4: Bytecode JIT Compiler with Inline Caching

BCSE307 Compiler Design project (VIT). A Python reference model of a stack-based bytecode VM with an inline cache (UNINIT → MONO → POLY → MEGA), shape versioning, and a tier-2 guarded fast path with deoptimisation, plus a small JavaScript front end checked against Node.

Pure Python 3 standard library; Node.js is only needed for the comparison against V8.

## Run

For the live demo, double-click `run_demo.command` (opens in Terminal, press Enter between steps).

```bash
python3 test_all.py                 # full regression suite: unit, end-to-end vs Node, invalid input, stress
python3 vm_ic_model.py              # 17 tests (TC1–TC12, IC1–IC5) + mono/poly/mega benchmark
python3 run_js.py examples/*.js     # compile JS -> our bytecode, run 3 ways, compare with Node
python3 demo.py                     # paced presentation walkthrough (--fast, --beat N)
node v8_compare.js                  # the same mono/poly/mega experiment inside V8
python3 mega_tuning.py              # megamorphic cache: capacity 4/8/16 x FIFO/LRU sweep
python3 threshold_sweep.py          # hot-loop threshold sweep
python3 benchmark.py                # median-of-5 timings used in the final report (run on an idle machine)
```

## Files

| File | What it is |
|---|---|
| `vm_ic_model.py` | VM, inline cache, tier 2 + deopt, tests and benchmarks |
| `jsc.py` | Compiler from a JavaScript subset to the VM's bytecode |
| `run_js.py` | Runs a `.js` file in Node and on our VM (baseline / + IC / + IC + tier 2) and compares output |
| `examples/` | Test programs: language features, mono / poly / mega / wide objects, deopt, edge cases |
| `tests/invalid/` | Invalid and failure programs (syntax error, undefined variable, unsupported features, ÷0, infinite loop, missing property) |
| `test_all.py` | Regression suite (34 checks) |
| `benchmark.py`, `threshold_sweep.py` | Median-of-N benchmark and hot-threshold sweep |
| `demo.py`, `v8_compare.js` | Live demo scripts |
| `mega_tuning.py` | Measured sweep of megamorphic cache capacity and eviction policy |
| `A4_Final_Report.docx` | **Final Review 3 report** (37 pages; open in Word and click Yes to update fields) |
| `report/` | Report generator: `bash report/build.sh` re-measures everything and rebuilds the report |
| `A4_Final_Presentation.pptx` | **Final deck** (23 slides, all results, no in-progress items) |
| `A4_Final_Presentation_Script.docx` | **Final presentation script**: what to say per slide, Q&A, demo steps, rehearsal checklist |
| `A4_Review2_*` | Review 2 report, slides and presentation script (`_Updated` = 23-slide Review 2 version) |
| `CLAUDE.md` | Architecture and development notes |
