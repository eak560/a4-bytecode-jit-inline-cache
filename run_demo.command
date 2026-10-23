#!/bin/bash
# One-click A4 demo: double-click this file in Finder (it opens in Terminal),
# or run ./run_demo.command. It waits for Enter between steps; --auto moves on by itself.
cd "$(dirname "$0")" || exit 1

step() {
  if [ "$PAUSE" = 1 ]; then
    read -r -p $'\n[Enter] for the next step ' _
  else
    sleep 4
  fi
  clear
}
PAUSE=1
[ "$1" = "--auto" ] && PAUSE=0

clear
echo "=== STEP 1: real JavaScript, checked against Node ==="
python3 run_js.py examples/*.js | tail -12
step

echo "=== STEP 2: tier 2 compiles a shortcut, a wrong guess triggers a deopt, the answer stays correct ==="
python3 demo.py --beat 6
step

echo "=== STEP 3: megamorphic cache tuning (takes ~15 seconds) ==="
python3 mega_tuning.py
echo
echo "=== Demo finished ==="
