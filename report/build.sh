#!/bin/bash
# Rebuild A4_Final_Report.docx from fresh measurements.
#   bash report/build.sh            full run (benchmark takes ~2 min on an idle machine)
#   bash report/build.sh --quick    reuse report/data/bench.json, re-measure everything else
# Close games/heavy apps first: timings are only meaningful on an idle machine.
set -e
cd "$(dirname "$0")"
ROOT=..
mkdir -p data fig
[ -d node_modules/docx ] || npm install --silent
if [ "$1" != "--quick" ] || [ ! -f data/bench.json ]; then
  python3 -B $ROOT/benchmark.py --json data/bench.json
fi
python3 -B $ROOT/test_all.py --json data/tests.json | tail -1
python3 -B $ROOT/threshold_sweep.py > data/threshold.txt
python3 -B $ROOT/run_js.py $ROOT/examples/deopt.js \
  | sed -E 's/[0-9]+\.[0-9]{3}s/  —   /; s/[0-9]+\.[0-9]+x$/  (too short to time)/; s/time  vs baseline//; s#\.\./examples#examples#' > data/deopt_run.txt
{ echo '$ python3 run_js.py tests/invalid/syntax_error.js'
  python3 -B $ROOT/run_js.py $ROOT/tests/invalid/syntax_error.js | grep -v '^$' | sed 's#\.\./tests#tests#'
  echo; echo '$ python3 run_js.py tests/invalid/division_by_zero.js'
  python3 -B $ROOT/run_js.py $ROOT/tests/invalid/division_by_zero.js | grep -E "output|our VM" | sed -E 's/ +[0-9.]+s +[0-9.]+x$//'
} > data/invalid_sample.txt
git -C $ROOT log --format='%h  %ad  %an  %s' --date=short > data/gitlog.txt
python3 - <<'PY'
import glob, json, os, platform, subprocess
os.chdir("..")
purpose = {
 "vm_ic_model.py": "VM, profiler, hidden classes, inline cache, tier 2 + deopt, TC/IC tests, synthetic benchmark",
 "jsc.py": "JavaScript-subset compiler: lexer, recursive-descent parser, code generation, lowering",
 "run_js.py": "Runs a .js file in Node and on the VM in 3 modes; compares output; per-site cache report",
 "test_all.py": "Regression suite: unit, end-to-end vs Node, invalid input, stress",
 "benchmark.py": "Median-of-N benchmark for the report (sections A–D)",
 "mega_tuning.py": "Megamorphic capacity × eviction-policy sweep",
 "threshold_sweep.py": "Hot-loop threshold sweep",
 "demo.py": "Paced presentation walkthrough (7 beats)",
 "v8_compare.js": "Same mono/poly/mega experiment inside V8",
 "run_demo.command": "One-click live demo",
 "examples/*.js": "7 JavaScript test programs",
 "tests/invalid/*.js": "7 invalid / failure programs",
}
rows = [{"file": f, "lines": sum(len(open(x).read().splitlines()) for x in glob.glob(f)), "purpose": p} for f, p in purpose.items()]
json.dump(rows, open("report/data/loc.json", "w"), indent=1)
try:
    import matplotlib; mpl = matplotlib.__version__
except ImportError:
    mpl = "not installed"
sh = lambda *c: subprocess.check_output(c, text=True).strip()
env = {"python": platform.python_version(), "node": sh("node", "--version"), "v8": sh("node", "-p", "process.versions.v8"),
       "os": "macOS " + sh("sw_vers", "-productVersion"), "cpu": sh("sysctl", "-n", "machdep.cpu.brand_string"),
       "mem": f"{int(sh('sysctl', '-n', 'hw.memsize')) // 2**30} GB RAM", "mpl": mpl}
json.dump(env, open("report/data/env.json", "w"), indent=1)
PY
python3 make_figures.py
node build_report.js $ROOT/A4_Final_Report.docx 2>/dev/null
python3 fix_docx.py $ROOT/A4_Final_Report.docx
echo "Done. Open A4_Final_Report.docx in Word and click Yes when it asks to update fields (fills the table of contents)."
