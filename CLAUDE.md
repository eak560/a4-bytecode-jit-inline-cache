# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Compiler Design course project "A4": a pure-Python (stdlib only, no dependencies) reference model of a stack-based bytecode VM plus an inline-cache (IC) state machine for property access. All code is in the single file `vm_ic_model.py`. The `.docx`/`.pptx` files are the Review 2 report, slides and presentation script, and their numbers come from this script's output.

This folder is its own git repository (private GitHub repo `eak560/a4-bytecode-jit-inline-cache`). The home directory `/Users/ehsan` is also a git repo; make sure git commands run here, not there.

## Running

```bash
python3 vm_ic_model.py
```

There is no test framework or build step. The script runs everything in order (~4 s): `run_tests()` (TC1–TC12, interpreter correctness), `run_ic_tests()` (IC1–IC5, cache state machine / invalidation / deopt), then `run_ic_benchmarks()` (100k-access mono/poly/mega timings + summary table). To run one section, call it directly, e.g.:

```bash
python3 -c "import vm_ic_model as m; m.run_ic_tests()"
```

Tests are inline `check(name, cond, detail)` calls inside those functions; to add a test, add a `check(...)` there with the next TC/IC number. `run_output.txt` is a saved older run (predates the IC1–IC5 section) — regenerate it rather than trusting it. Benchmark timings are wall-clock and vary per run; the script's stated contract is that every printed number is measured, never hard-coded, so don't fabricate or hand-edit results in the report/slides.

## Tests and benchmarks

- `python3 test_all.py` is the regression suite (unit, end-to-end vs Node, `tests/invalid/` negative cases with expected diagnostics, stress); keep it passing. Add a negative case by dropping a file in `tests/invalid/` and an entry in its `EXPECTED` dict.
- `python3 benchmark.py --json out.json` produces the median-of-5 numbers used in the final report; timings are only meaningful on an idle machine (a game or browser load distorts them badly). Hit rates and mismatch counts are deterministic.

## JavaScript front end and demos

- `jsc.py` compiles a small JavaScript subset (let/if/while/for, integers, object and constant-array literals, `p.x`, `console.log`) to the VM bytecode. The ISA only has `LT`, so `>`, `<=`, `==`, `%` etc. are lowered using compiler-generated temp locals (`$tN` slots). Object/array literals are built at compile time into the VM's object table. The docstring lists what's unsupported.
- `python3 run_js.py examples/*.js` runs each file in Node (the reference output) and on our VM in three modes (baseline / +IC / +IC+tier 2). Every mode must match Node; it exits non-zero otherwise. `--bytecode` dumps the compiled code.
- `python3 demo.py [--fast | --beat N]` is the paced presentation walkthrough; `v8_compare.js` shows V8's own mono/poly/mega slowdown.
- Measured fact: with small objects (6 fields) the IC is *slower* than the baseline linear scan in Python; it only wins on wide objects (`examples/points_wide.js`, and the 200-field benchmark). Keep that caveat when quoting speedups.

## Architecture

**VM (`VM.run`)** — a `(op, arg)` tuple-list interpreter: PUSH/POP, ADD/SUB/MUL/DIV (integer `//`, div-by-zero raises `VMError`), LOAD/STORE (locals), LOADOBJ (index into `self.objects`), JMP/JZ, LT, PRINT (records top of stack without popping), GETFIELD, HALT. Backward jumps increment `back_edge_counts`; reaching `hot_threshold` marks the loop head in `hot_flags`. `max_steps` guards against infinite loops.

**GETFIELD has three execution paths**, chosen per call site (keyed by bytecode `pc`):
1. Tier-2: if `pc in self.compiled`, a guarded direct load checking `(shape.id, shape.version)`; on guard failure `deoptimize()` deletes the compiled entry, hard-resets that site's `ICEntry` to UNINIT and re-does the access via the IC.
2. IC (`ic_mode=True`): `ic_getprop` with a per-site `ICEntry`; with `tier2=True`, a site is compiled once any loop is hot and the site is MONO.
3. Baseline: `baseline_getprop`, a linear scan of property names.

**Hidden classes** — `Shape` is interned by property-name tuple via `__new__` + `_registry` (a class-level global, so shapes persist across tests in one process; `small_objects` uses `p*` names to avoid colliding with benchmark `f*` shapes). `Obj` stores `shape` + a parallel `values` list. `mutate_shape` re-lays-out objects in place and bumps `shape.version`; IC entries store `(shape_id, version, offset)` and treat a version mismatch as a miss — this is the lazy-invalidation mechanism.

**IC state machine** — UNINIT → MONO (1 entry) → POLY (≤4 entries) → MEGA. MEGA moves entries into an `OrderedDict` bounded by `MEGA_CACHE_CAPACITY` (4) and evicted per `MEGA_POLICY` ("FIFO" default, or "LRU"). Both are module globals read at call time, so `mega_tuning.py` sweeps them by assignment; keep the defaults at 4/FIFO so the Review 2 numbers and tests stay reproducible. With >4 shapes the default thrashes and is expected to be *slower* than baseline; the sweep showed capacity (not policy) fixes it (16 slots → 100% hits, ~1.5×).

The final report `A4_Final_Report.docx` is generated by `bash report/build.sh` (docx-js + matplotlib, reads only measured data in `report/data/`); edit `report/build_report.js`, not the .docx. The final deck is `A4_Final_Presentation.pptx`; it was generated from the Review 2 deck by XML edits, so edit it in PowerPoint rather than regenerating.

**Benchmarks** — `build_loop_program(n)` emits a fixed loop where GETFIELD always sits at index 8 (`GETFIELD_PC`; the docstring saying "index 6" is stale). If you change that program's layout, update `GETFIELD_PC` and the JZ exit target. Each workload runs baseline and IC on the same objects and counts output mismatches (differential testing — must be 0). `N_DUMMY_PROPS = 200` deliberately makes the uncached linear scan expensive.
