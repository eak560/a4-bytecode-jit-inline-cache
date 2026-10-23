// v8_compare.js -- the same experiment, run on a real engine (V8, inside Node).
//
//   node v8_compare.js
//
// We read o.x in a hot loop over objects of 1, 3 and 16 different "shapes"
// (hidden classes). V8 has the same UNINIT -> MONO -> POLY -> MEGA inline
// cache as our model (and also switches to megamorphic after 4 shapes), so
// the same pattern should show up: mono fast, poly a bit slower, mega slowest.
// Absolute times are NOT comparable with our Python model -- only the shape
// of the result is.

function makeObjects(nShapes, n) {
  const objs = [];
  for (let i = 0; i < n; i++) {
    const k = i % nShapes;
    const o = {};
    for (let j = 0; j < k; j++) o["f" + j] = j; // k filler props first -> distinct shape
    o.x = 1;
    objs.push(o);
  }
  return objs;
}

// One separate function per workload, so each has its OWN o.x call site
// (an inline cache lives at a call site -- sharing one would mix the results).
function sumMono(objs) { let s = 0; for (let i = 0; i < objs.length; i++) s += objs[i].x; return s; }
function sumPoly(objs) { let s = 0; for (let i = 0; i < objs.length; i++) s += objs[i].x; return s; }
function sumMega(objs) { let s = 0; for (let i = 0; i < objs.length; i++) s += objs[i].x; return s; }

const N = 1_000_000, ROUNDS = 50;
const rows = [
  ["Monomorphic (1 shape)", 1, sumMono],
  ["Polymorphic (3 shapes)", 3, sumPoly],
  ["Megamorphic (16 shapes)", 16, sumMega],
];

console.log(`V8 ${process.versions.v8}: ${ROUNDS} x ${N.toLocaleString()} reads of o.x per workload\n`);
let monoMs;
for (const [label, shapes, fn] of rows) {
  const objs = makeObjects(shapes, N);
  fn(objs); fn(objs); // warm up: let the IC settle and the JIT kick in
  const t0 = process.hrtime.bigint();
  let check = 0;
  for (let r = 0; r < ROUNDS; r++) check += fn(objs);
  const ms = Number(process.hrtime.bigint() - t0) / 1e6;
  monoMs ??= ms;
  const ok = check === N * ROUNDS ? "correct" : "WRONG";
  console.log(`${label.padEnd(26)} ${ms.toFixed(0).padStart(6)} ms   ${(ms / monoMs).toFixed(2)}x mono time   (${ok})`);
}
