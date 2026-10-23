// Builds the A4 Review 3 final report (.docx) from measured data files.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, ImageRun, PageBreak, Footer, Header, PageNumber,
  TableOfContents, LevelFormat, TabStopType,
} = require("docx");

const HERE = __dirname;
const OUT = process.argv[2];
const B = JSON.parse(fs.readFileSync(path.join(HERE, "data", "bench.json"), "utf8"));
const THRESH = fs.readFileSync(path.join(HERE, "data", "threshold.txt"), "utf8");
const GITLOG = fs.readFileSync(path.join(HERE, "data", "gitlog.txt"), "utf8").trim().split("\n");
const LOC = JSON.parse(fs.readFileSync(path.join(HERE, "data", "loc.json"), "utf8"));
const ENV = JSON.parse(fs.readFileSync(path.join(HERE, "data", "env.json"), "utf8"));

const f2 = (x) => x.toFixed(2);
const pct = (x) => (x * 100).toFixed(1) + "%";
const A = Object.fromEntries(B.A.map((r) => [r.workload, r]));
const C = Object.fromEntries(B.C.map((r) => [r.program.replace(".js", ""), r]));
const M = (cap, pol) => B.B.find((r) => r.capacity === cap && r.policy === pol);
const testRows = JSON.parse(fs.readFileSync(path.join(HERE, "data", "tests.json"), "utf8"))
  .map((r) => ({ ...r, result: r.passed ? "PASS" : "FAIL" }));
const policyGap = Math.max(...[4, 8, 16].map((c) => Math.abs(M(c, "FIFO").speedup - M(c, "LRU").speedup)));
const verdict = (x) => (x >= 1.05 ? "wins" : x >= 0.95 ? "roughly breaks even" : "still loses");
const nPass = testRows.filter((r) => r.result === "PASS").length;
const threshBlocks = THRESH.trim().split("\n\n").map((b) => {
  const lines = b.split("\n");
  return { title: lines[0], rows: lines.filter((l) => /^\s+\d/.test(l)).map((l) => l.trim().split(/\s+/)) };
});

// ---------------- styling helpers ----------------
const INK = "3A2E2F", TEAL = "00827C", HEAD = "4E3B3C", SHADE = "EEF7F6", CODEBG = "F4F2F2";
const FONT = "Calibri", HFONT = "Cambria", MONO = "Courier New";
const CONTENT_W = 9026;
let figN = 0, tabN = 0;

function runs(text, base = {}) {
  // **bold**, *italic*, `code`
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), bold: true, ...base }));
    else if (t.startsWith("`")) out.push(new TextRun({ text: t.slice(1, -1), font: MONO, size: 19, ...base }));
    else out.push(new TextRun({ text: t.slice(1, -1), italics: true, ...base }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out;
}
const P = (text, opts = {}) => new Paragraph({ children: runs(text), spacing: { after: 120, line: 288 }, alignment: AlignmentType.JUSTIFIED, ...opts });
const HEADINGS = [];
const H1 = (t) => { HEADINGS.push([1, t]); return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)], pageBreakBefore: true }); };
const H2 = (t) => { HEADINGS.push([2, t]); return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] }); };
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)] });
const BUL = (t, level = 0) => new Paragraph({ children: runs(t), numbering: { reference: "bullets", level }, spacing: { after: 60, line: 276 } });
const NUM = (t, ref = "num1") => new Paragraph({ children: runs(t), numbering: { reference: ref, level: 0 }, spacing: { after: 60, line: 276 } });

function caption(kind, text) {
  const n = kind === "Figure" ? ++figN : ++tabN;
  return new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { before: 60, after: 200 },
    children: [new TextRun({ text: `${kind} ${n}: `, bold: true, size: 19, color: HEAD }), new TextRun({ text, italics: true, size: 19, color: "5A4E4F" })],
  });
}
function tableCaption(text) {
  const n = ++tabN;
  return new Paragraph({
    keepNext: true, spacing: { before: 160, after: 80 },
    children: [new TextRun({ text: `Table ${n}: `, bold: true, size: 19, color: HEAD }), new TextRun({ text, italics: true, size: 19, color: "5A4E4F" })],
  });
}

const border = { style: BorderStyle.SINGLE, size: 4, color: "D9CFCF" };
const borders = { top: border, left: border, bottom: border, right: border };
function cell(text, width, { header = false, fill, align, mono = false } = {}) {
  return new TableCell({
    borders, width: { size: width, type: WidthType.DXA },
    shading: header ? { fill: HEAD, type: ShadingType.CLEAR, color: "auto" } : fill ? { fill, type: ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({
      alignment: align || AlignmentType.LEFT,
      children: header ? [new TextRun({ text, bold: true, color: "FFFFFF", size: 19 })]
        : runs(String(text), mono ? { font: MONO, size: 17 } : { size: 19 }),
    })],
  });
}
function table(headers, rows, widths, opts = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  return [new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, widths[i], { header: true })) }),
      ...rows.map((r, ri) => new TableRow({
        children: r.map((v, i) => cell(v, widths[i], {
          fill: opts.fill ? opts.fill(r, i, ri) : (ri % 2 ? "FAF8F8" : undefined),
          align: opts.align && opts.align[i], mono: opts.mono && opts.mono[i],
        })),
      })),
    ],
  }), new Paragraph({ spacing: { after: 120 }, children: [] })];
}
function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}
function figure(name, text, widthIn = 6.2) {
  const file = path.join(HERE, "fig", name);
  const { w, h } = pngSize(file);
  const pw = Math.round(widthIn * 96);
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120 },
      children: [new ImageRun({ type: "png", data: fs.readFileSync(file), transformation: { width: pw, height: Math.round(pw * h / w) },
        altText: { title: text, description: text, name } })] }),
    caption("Figure", text),
  ];
}
function code(lines, size = 17) {
  return lines.map((l, i) => new Paragraph({
    shading: { fill: CODEBG, type: ShadingType.CLEAR, color: "auto" },
    spacing: { after: 0, line: 240, before: i === 0 ? 80 : 0 }, indent: { left: 200, right: 200 },
    keepLines: true, keepNext: i < lines.length - 1,
    children: [new TextRun({ text: l || " ", font: MONO, size, color: INK })],
  })).concat([new Paragraph({ spacing: { after: 120 }, children: [] })]);
}
const callout = (text) => new Paragraph({
  children: runs(text), spacing: { before: 120, after: 160, line: 276 },
  shading: { fill: SHADE, type: ShadingType.CLEAR, color: "auto" },
  indent: { left: 140, right: 140 },
});

// ---------------- content ----------------
const MEMBERS = [
  ["1", "24BCT0093", "Chilukuri Charith Reddy", "VM & hot-path integration"],
  ["2", "24BCE0334", "Vatsal Sharma", "Profiler & hot-code detection"],
  ["3", "24BCE0506", "Mayan Manit", "Inline-cache integration & hit-rate measurement"],
  ["4", "24BCT0089", "Ehsan Abdulkhader", "Tier-2 fast path, deoptimisation, JS front end & evaluation"],
];

const cover = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 600, after: 120 }, children: [new TextRun({ text: "VELLORE INSTITUTE OF TECHNOLOGY", bold: true, size: 28, color: HEAD, font: HFONT })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 }, children: [new TextRun({ text: "BCSE307 — Compiler Design", size: 26, color: INK })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: "Project Review 3 — Final Report", size: 26, color: TEAL, bold: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 }, children: [new TextRun({ text: "Bytecode JIT Compiler with Inline Caching", bold: true, size: 48, color: HEAD, font: HFONT })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 700 }, children: [new TextRun({ text: "A stack-based bytecode VM with hidden classes, a four-state inline cache, a guarded tier-2 fast path with deoptimisation, and a JavaScript-subset front end verified against V8", italics: true, size: 22, color: "5A4E4F" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: "Project ID: A4", bold: true, size: 24 })] }),
  ...table(["S.No", "Register No.", "Name", "Technical ownership"], MEMBERS, [700, 1600, 2700, 4026]),
  new Paragraph({ spacing: { before: 500, after: 100 }, children: [new TextRun({ text: "Team number: ____________        Review date: ____________", size: 22 })] }),
  new Paragraph({ spacing: { after: 100 }, children: [new TextRun({ text: "Faculty / Evaluator: ________________________________", size: 22 })] }),
  new Paragraph({ spacing: { after: 100 }, children: [new TextRun({ text: "Repository: github.com/eak560/a4-bytecode-jit-inline-cache (private; access on request)", size: 22 })] }),
];

const declaration = [
  new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, children: [new TextRun("Declaration")] }),
  P("We, the undersigned members of Team A4, declare that this report and the accompanying software are our original work, carried out for the course BCSE307 Compiler Design at Vellore Institute of Technology. All external sources — books, papers, documentation and software tools — are acknowledged in the References section. No code was copied from other student teams. Results reported here were produced by running the scripts in the project repository; every timing and count is measured output, not an estimate."),
  new Paragraph({ spacing: { before: 400 }, children: [] }),
  ...table(["Name", "Register No.", "Signature", "Date"], MEMBERS.map((m) => [m[2], m[1], "", ""]), [3000, 1800, 2426, 1800]),
];

// Static contents page: page numbers come from data/toc_pages.json, written by
// paginate.py after a first PDF export (so the page always shows, no field update).
const TOC_PAGES = fs.existsSync(path.join(HERE, "data", "toc_pages.json"))
  ? JSON.parse(fs.readFileSync(path.join(HERE, "data", "toc_pages.json"), "utf8")) : {};
const toc = [new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, children: [new TextRun("Contents")] })];
function fillToc() {
  for (const [level, text] of HEADINGS) {
    toc.push(new Paragraph({
      tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_W, leader: "dot" }],
      spacing: { before: level === 1 ? 100 : 0, after: 20 },
      indent: { left: level === 1 ? 0 : 360 },
      children: [new TextRun({ text, bold: level === 1, size: level === 1 ? 21 : 19 }),
                 new TextRun({ text: "\t" + (TOC_PAGES[text] || "–"), bold: level === 1, size: level === 1 ? 21 : 19 })],
    }));
  }
}

const abstract = [
  H1("1. Abstract"),
  P(`Dynamically typed languages such as JavaScript look up object properties by name at run time, which makes the simplest implementation — scanning the property list on every access — slow. Production engines such as V8 solve this with hidden classes, inline caches and tiered just-in-time (JIT) compilation with deoptimisation. This project builds a complete, measurable reference implementation of those ideas. It consists of (i) a stack-based bytecode virtual machine with a 15-opcode instruction set and back-edge loop profiling; (ii) hidden classes ("shapes") with version numbers for lazy invalidation; (iii) a per-call-site inline cache that moves through the UNINIT, MONO, POLY and MEGA states; (iv) a tier-2 path that compiles hot monomorphic property reads into guarded direct loads and deoptimises safely when a guard fails; and (v) jsc.py, a single-pass recursive-descent compiler from a JavaScript subset to the VM's bytecode.`),
  P(`Correctness is established by differential testing: every program runs on the baseline interpreter, with the inline cache, and with the cache plus tier 2, and all outputs are compared with each other and with Node.js (V8). The regression suite passes ${nPass} of ${testRows.length} checks, covering unit, end-to-end, invalid-input and stress cases. On 200-field objects the inline cache is ${f2(A.mono.speedup)}× faster than the baseline for monomorphic sites and ${f2(A.poly.speedup)}× for polymorphic sites (median of ${B.reps} runs); on a 16-shape megamorphic site with 4 slots it is ${f2(A.mega.speedup)}×. A capacity/eviction sweep shows that capacity, not eviction policy, fixes the megamorphic case (16 slots: 100% hits, ${f2(M(16, "FIFO").speedup)}×). On small 6-field objects the cache costs more than the scan it replaces, while tier 2 recovers the loss — an honest result that mirrors why real engines compile cached accesses to machine code.`),
];

const intro = [
  H1("2. Introduction and Motivation"),
  H2("2.1 Context"),
  P("A compiler for a statically typed language knows, when it compiles `p.x`, exactly where field `x` sits in memory, and can emit a single load instruction. A JavaScript engine does not: objects are created and extended at run time, and the same line of code may see objects of many different layouts. The naive implementation treats every object as a dictionary and looks the property up by name on every access. Because property access is among the most frequent operations in real programs, this cost dominates execution time."),
  P("The techniques that make modern JavaScript fast were developed over several decades of research on Smalltalk and Self and are now standard in engines such as V8 (Chrome, Node.js), SpiderMonkey (Firefox) and JavaScriptCore (Safari): objects share hidden classes that describe their layout; each property-access site keeps an inline cache that remembers the layouts it has seen; and frequently executed code is recompiled into fast, specialised code that relies on assumptions, with deoptimisation as the safety net when an assumption breaks."),
  H2("2.2 Need and beneficiaries"),
  P("These mechanisms are usually taught as diagrams; real engines are millions of lines of C++ in which they are hard to observe. A small, complete and instrumented implementation lets students and instructors see each mechanism working, measure its effect, and break it deliberately to understand why it is built the way it is. The beneficiaries are compiler-design students, instructors who need a runnable teaching artefact, and developers who want an intuition for why their JavaScript code is fast or slow (for example, why constructing objects with a consistent property order matters)."),
  H2("2.3 Relevance to compiler design"),
  P("The project touches most stages of a compiler and runtime: lexical analysis (a regular-expression lexer), syntax analysis (a recursive-descent parser for an expression grammar with precedence), intermediate representation (stack bytecode), code generation with back-patching of jump targets, lowering of operators to a restricted instruction set, interpretation (fetch–decode–execute), run-time profiling, run-time code specialisation (tier 2) and speculative optimisation with deoptimisation. It therefore connects the front-end theory of the course with the run-time techniques used in production compilers."),
];

const objectives = [
  H1("3. Problem Statement, Objectives, Scope and Limitations"),
  H2("3.1 Problem statement"),
  P("Design, implement and evaluate a bytecode execution engine that accelerates dynamic property access using hidden classes, inline caching and a guarded tier-2 fast path with deoptimisation, such that every optimised execution produces exactly the same output as an unoptimised reference interpreter — and demonstrate it on real JavaScript programs whose output is checked against a production engine."),
  H2("3.2 Measurable objectives and compliance"),
  tableCaption("Final objective-compliance matrix"),
  ...table(["#", "Objective (from Review 1)", "Measure", "Status", "Evidence"], [
    ["O1", "Stack-based VM and bytecode format", "All opcodes implemented and tested", "Met", "15 opcodes; TC1–TC12 pass"],
    ["O2", "Baseline interpreter as correctness oracle", "All baseline tests pass", "Met", "TC1–TC12, 12/12"],
    ["O3", "Hot-code detection", "Hot loop flagged at threshold; threshold configurable", "Met", "TC11; VM(hot_threshold); threshold_sweep.py"],
    ["O4", "Inline caching (mono/poly/mega) with invalidation", "Each state reached; stale entries rejected", "Met", "IC1–IC4; mega_tuning.py"],
    ["O5", "Tier-2 fast path with deoptimisation", "Guarded load used; deopt resets IC; 0 wrong answers", "Met (model)", `IC5: 1 deopt, 92 fast-path reads`],
    ["O6", "Benchmarking and differential testing", "0 mismatches across workloads; speedup measured", "Met", `${nPass}/${testRows.length} checks; benchmark.py`],
    ["O7", "Extension: JavaScript front end", "Programs compiled and matched against Node", "Met", "jsc.py; 7 programs × 3 modes = Node"],
  ], [500, 2500, 2526, 1100, 2400], { fill: (r, i) => (i === 3 ? "DDF1EF" : undefined) }),
  P("O5 is met in the reference implementation: the guarded fast path and deoptimisation are implemented, executed and tested in Python. Emitting the same guards as native machine code (for example with asmjit) is outside the delivered scope and is listed as future work (Section 13)."),
  H2("3.3 Closure of Review 2 action items"),
  P("Review 2 ended with six next steps. Their final status is:"),
  tableCaption("Review 2 next steps and their closure"),
  ...table(["Review 2 next step", "Outcome in Review 3", "Evidence"], [
    ["Exercise the deoptimisation path end to end", "Closed — deopt runs inside the VM loop, resets the site to UNINIT and recompiles", "IC5; examples/deopt.js matches Node"],
    ["Tune the megamorphic cache", "Closed — capacity × policy sweep; capacity fixes it", "mega_tuning.py, Section 10.3"],
    ["Make the hot threshold configurable and sweep it", "Closed — VM(hot_threshold=…); swept 1–100", "threshold_sweep.py, Section 10.5"],
    ["Run the full benchmark for final numbers", "Closed — median of 5 runs on one machine", "benchmark.py, Section 10"],
    ["Draft the final report", "Closed — this document", "—"],
    ["Emit IC guards in native code", "Not delivered — future work", "Section 13"],
  ], [3000, 3626, 2400]),
  H2("3.4 Scope"),
  BUL("**In scope:** the bytecode VM and profiler; hidden classes with versioning; the inline-cache state machine; tier-2 guarded loads and deoptimisation; a compiler for a JavaScript subset; differential testing against Node; benchmarks and parameter sweeps."),
  BUL("**Out of scope:** generation of native machine code; garbage collection; the full JavaScript language (strings, functions, closures, prototypes, property writes)."),
  H2("3.5 Limitations (summary)"),
  P("The engine is a Python reference model, so its timings show algorithmic savings (fewer comparisons per property read), not machine-code speed. The JavaScript subset is deliberately small. Section 11 lists every unsupported construct and known behavioural difference from JavaScript."),
];

const background = [
  H1("4. Background and Related Work"),
  H2("4.1 Hidden classes (shapes)"),
  P("Self [3] introduced *maps*: objects created with the same properties in the same order share one map that records the offset of each property, so an object needs to store only its values plus a pointer to its map. V8 calls these hidden classes or *shapes* and builds them as transition trees as properties are added [9]. Two objects `{x, y}` and `{y, x}` therefore have different shapes, because `x` is at a different offset."),
  H2("4.2 Inline caches"),
  P("Deutsch and Schiffman [2] observed that a given call site in Smalltalk usually sees receivers of the same class, and cached the lookup result directly at the call site — an *inline cache*. Hölzle, Chambers and Ungar [4] generalised this to *polymorphic inline caches* (PICs) that hold a short list of (class, target) pairs, and showed that sites with too many classes (megamorphic sites) should fall back to a slower generic lookup. Modern engines use exactly this monomorphic / polymorphic / megamorphic classification; V8 caps polymorphic caches at four entries and backs megamorphic sites with a global shared cache [9]."),
  H2("4.3 Tiered compilation and deoptimisation"),
  P("A JIT compiler [6] starts in an interpreter, profiles which code is hot and which types it sees, and recompiles hot code into specialised machine code. Specialisation is speculative: the code assumes, for example, that an object has a particular shape. Hölzle, Chambers and Ungar [5] introduced *dynamic deoptimisation*, which transfers execution back to unoptimised code when an assumption fails. Trace-based JITs such as TraceMonkey [7] and partial-evaluation systems such as Truffle/Graal [8] use the same guard-and-deoptimise pattern."),
  H2("4.4 Comparison and identified gap"),
  tableCaption("Comparison with production engines and textbook coverage"),
  ...table(["Aspect", "V8 / production engines", "Compiler textbooks [1]", "This project"], [
    ["Hidden classes", "Yes (transition trees)", "Not covered", "Yes (interned shapes + version)"],
    ["Inline caches", "Mono/poly/mega + shared cache", "Not covered", "Mono/poly/mega, bounded table"],
    ["Tier-2 + deopt", "Optimising compiler (TurboFan)", "Not covered", "Guarded direct load + deopt"],
    ["Front end", "Full JavaScript", "Covered in theory", "JS subset, recursive descent"],
    ["Observability", "Hard (millions of LOC)", "—", "Every hit, miss, compile, deopt counted"],
    ["Correctness evidence", "Large test suites", "—", "Differential vs baseline and vs V8"],
  ], [1700, 2500, 2026, 2800]),
  P("The gap this project addresses is a *small, complete and measurable* implementation in which each of these mechanisms can be executed, counted and compared, with the production engine used as the correctness reference."),
];

const reqs = [
  H1("5. Requirements and Technology Stack"),
  H2("5.1 Functional requirements"),
  NUM("Execute stack bytecode correctly, including arithmetic, locals, jumps, comparison, output and property access.", "num1"),
  NUM("Detect hot loops by counting backward jumps.", "num1"),
  NUM("Cache property offsets per access site and transition through UNINIT, MONO, POLY and MEGA.", "num1"),
  NUM("Never return a stale offset after a shape changes.", "num1"),
  NUM("Compile hot monomorphic sites to guarded loads and deoptimise on guard failure without changing output.", "num1"),
  NUM("Compile a JavaScript subset to bytecode and report clear errors for invalid or unsupported input.", "num1"),
  NUM("Check every optimised run against the baseline and against Node.js.", "num1"),
  H2("5.2 Non-functional requirements"),
  BUL("**Reproducibility:** fixed random seeds; single-command test and benchmark scripts; no third-party Python packages."),
  BUL("**Observability:** every hit, miss, compile, fast-path read and deopt is counted."),
  BUL("**Safety:** a step limit stops runaway programs; errors are reported, never silently wrong."),
  H2("5.3 Technology stack and environment"),
  tableCaption("Software, hardware and test environment"),
  ...table(["Item", "Version / detail", "Role"], [
    ["Python", ENV.python, "VM, compiler, tests, benchmarks (standard library only)"],
    ["Node.js / V8", `${ENV.node} / V8 ${ENV.v8}`, "Reference output; V8 comparison"],
    ["Operating system", ENV.os, "Test and benchmark machine"],
    ["Hardware", ENV.cpu, "Apple Silicon laptop, " + ENV.mem],
    ["matplotlib", ENV.mpl, "Report figures only (not needed to run the project)"],
    ["Git / GitHub", "private repository", "Version control and submission"],
  ], [2000, 3300, 3726]),
  H2("5.4 Test programs"),
  P("Seven JavaScript programs in `examples/` (language features, monomorphic, polymorphic, megamorphic and wide-object workloads, a deoptimisation scenario and boundary cases) and seven invalid programs in `tests/invalid/`. The synthetic benchmarks generate objects with 200 filler fields using fixed seeds (42 for benchmarks, 7 for stress tests)."),
];

const design = [
  H1("6. System Design"),
  H2("6.1 Architecture"),
  P("Figure 1 shows the final architecture. A JavaScript file is compiled by `jsc.py` into bytecode plus a table of pre-built objects. The runtime in `vm_ic_model.py` executes it; the profiler marks hot loops; property reads go through the inline cache and, when hot and monomorphic, through tier 2. Node.js runs the same file, and the outputs are compared line by line."),
  ...figure("fig_architecture.png", "Final architecture and data flow"),
  H2("6.2 Modules and interfaces"),
  tableCaption("Modules, responsibilities and interfaces"),
  ...table(["Module", "File / entry point", "Input → output", "Owner"], [
    ["Front end (lexer, parser, code generator)", "jsc.py · compile_js(src)", "JS text → (bytecode, compiler state)", "Member 4"],
    ["Bytecode VM / interpreter", "vm_ic_model.py · VM.run()", "bytecode → output list", "Member 1"],
    ["Profiler (hot-loop detection)", "VM.run() back-edge counters", "jumps → hot_flags", "Member 2"],
    ["Hidden classes", "Shape, Obj, make_object, mutate_shape", "property dict → shaped object", "Member 3"],
    ["Inline cache", "ICEntry, ic_getprop()", "(site, object, name) → value", "Member 3"],
    ["Tier 2 and deoptimisation", "VM.compiled, VM.deoptimize()", "hot MONO site → guarded load", "Member 4"],
    ["Evaluation harness", "run_js.py, test_all.py, benchmark.py, mega_tuning.py, threshold_sweep.py", "programs → reports", "Member 4"],
  ], [2400, 2700, 2326, 1600]),
  H2("6.3 Core data structures"),
  BUL("**Instruction:** a tuple `(op, arg)`, e.g. `(\"GETFIELD\", \"x\")`. A program is a list of instructions; the program counter `pc` indexes it."),
  BUL("**Shape:** `id`, ordered `props` list and `version`. Shapes are interned in a registry keyed by the property-name tuple, so equal layouts share one shape object."),
  BUL("**Obj:** a `shape` reference and a parallel `values` list (`__slots__` to keep it compact)."),
  BUL("**ICEntry (one per GETFIELD site, keyed by pc):** `state`, `entries` — a list of `(shape_id, version, offset)` for MONO/POLY — and `mega_table`, an ordered dictionary bounded by `MEGA_CACHE_CAPACITY`."),
  BUL("**Tier-2 table:** `VM.compiled`, a map from pc to `(shape_id, version, offset)` — the guard and the offset of the compiled load."),
  H2("6.4 Execution paths of GETFIELD"),
  P("Property reads are the focus of every optimisation. Figure 2 shows the three paths a GETFIELD can take, chosen per site."),
  ...figure("fig_getfield.png", "The three execution paths of a GETFIELD instruction"),
  H2("6.5 Key design decisions"),
  tableCaption("Design decisions and their justification"),
  ...table(["Decision", "Alternative considered", "Justification"], [
    ["Stack-based bytecode", "Register-based bytecode", "Simpler code generation (no register allocation); used by the JVM, CPython and WebAssembly"],
    ["Cache keyed by bytecode address (pc)", "One global cache", "Matches the *inline* in inline cache: sites behave differently and must not pollute each other"],
    ["Version number on shapes, checked on use", "Flush every cache on mutation", "Lazy invalidation is O(1) per access and needs no list of dependent caches"],
    ["Hard reset to UNINIT on deopt", "Append the new shape", "A failed speculation means the site's history is unreliable; resetting avoids repeated wrong guesses"],
    ["Compile only MONO sites", "Compile POLY sites as guard chains", "One guard keeps the fast path minimal and the deopt logic simple"],
    ["Single-pass compiler with back-patching", "Build an AST, then generate code", "Fewer data structures; jump targets are patched once known"],
    ["Bounded MEGA table", "Unbounded dictionary", "Models real size-limited caches so megamorphic behaviour can be studied"],
    ["Python standard library only", "C/C++ with asmjit", "Fast iteration and full instrumentation; correctness first, native code as future work"],
  ], [2500, 2300, 4226]),
];

const algos = [
  H1("7. Algorithms and Methodology"),
  H2("7.1 Bytecode execution and instruction set"),
  P("The VM is a fetch–decode–execute loop over a value stack, an array of local slots and an object table. Each instruction is dispatched by opcode; a step counter raises an error if a program exceeds `max_steps`, so infinite loops terminate safely."),
  tableCaption("Instruction set (15 opcodes)"),
  ...table(["Group", "Opcodes", "Stack effect"], [
    ["Stack", "PUSH v, POP", "push constant; discard top"],
    ["Arithmetic", "ADD, SUB, MUL, DIV", "pop b, pop a, push a∘b (DIV is integer; ÷0 raises VMError)"],
    ["Locals", "LOAD k, STORE k", "push local k; pop into local k"],
    ["Control", "JMP t, JZ t, LT", "jump; pop and jump if 0; pop b, a, push (a<b ? 1 : 0)"],
    ["I/O", "PRINT, HALT", "record top of stack; stop"],
    ["Objects", "LOADOBJ, GETFIELD name", "pop index, push object; pop object, push property value"],
  ], [1600, 2600, 4826]),
  H2("7.2 Hot-loop detection"),
  P("A backward jump (target ≤ current pc) is a loop back-edge. The VM increments a counter for the target; when it reaches `hot_threshold` the loop head is added to `hot_flags`. Counting only back-edges costs one comparison per jump and identifies exactly the code that repeats. TC11 verifies it; Section 10.5 sweeps the threshold."),
  H2("7.3 Inline-cache lookup and state transitions"),
  P("Figure 3 shows the state machine of one site. The lookup algorithm treats an entry as a hit only if both the shape id and the shape version match:"),
  ...figure("fig_states.png", "Inline-cache state machine of one GETFIELD site", 6.0),
  ...code([
    "ic_getprop(cache, obj, name):",
    "    if cache.state == MEGA:",
    "        entry = cache.mega_table.get(obj.shape.id)",
    "        if entry and entry.version == obj.shape.version: return hit",
    "        offset = linear_scan(obj, name); insert; evict oldest (FIFO) or LRU if full",
    "    for (sid, ver, off) in cache.entries:              # at most 4",
    "        if sid == obj.shape.id and ver == obj.shape.version: return obj.values[off]",
    "    offset = linear_scan(obj, name)                    # miss",
    "    replace any stale entry for this shape; append (id, version, offset)",
    "    state = MONO if 1 entry, POLY if 2-4, else move entries into mega_table -> MEGA",
  ]),
  H2("7.4 Lazy invalidation by shape versioning"),
  P("`mutate_shape` inserts a property into an existing shape in place (modelling a class gaining a field after objects exist), re-lays-out every object of that shape and increments `shape.version`. Nothing else is updated. Any cache entry recorded under the old version now fails the version comparison and is re-resolved on its next use. IC4 demonstrates that without this check the cache would return the wrong value (2 instead of 3)."),
  H2("7.5 Tier-2 guarded load and deoptimisation"),
  P("After a GETFIELD is resolved by the cache, if any loop is hot and the site is MONO, the VM records `compiled[pc] = (shape_id, version, offset)`. Later executions of that site skip the cache entirely:"),
  ...code([
    "if pc in compiled:",
    "    sid, ver, off = compiled[pc]",
    "    if obj.shape.id == sid and obj.shape.version == ver:   # the guard",
    "        value = obj.values[off]                           # direct load",
    "    else:                                                 # deoptimise",
    "        del compiled[pc]; cache.reset() -> UNINIT",
    "        value = ic_getprop(cache, obj, name)               # safe re-execution",
  ]),
  P("Because the deoptimised access is re-executed through the cache and interpreter, the result is identical to the baseline. After a deopt the site may become MONO again and be recompiled for the new shape (IC5 compiles twice)."),
  H2("7.6 Front end: lexing, parsing and code generation"),
  P("**Lexing.** One regular expression with named groups recognises whitespace and comments, integers, identifiers and operators (longest operators first, e.g. `===` before `==`). Each token records its line number for error messages."),
  P("**Parsing.** A hand-written recursive-descent parser implements the grammar in Appendix C, one function per precedence level (comparison < additive < multiplicative < unary < postfix < primary). Code is emitted during parsing; there is no separate AST."),
  P("**Back-patching.** For `if`, `while` and `for`, the parser emits `JZ` with an unknown target, records its index, compiles the body and then patches the target. A `for` loop's update clause is skipped and compiled after the body by re-parsing its token range."),
  P("**Lowering.** The instruction set has only `LT`, so other operators are rewritten using compiler-generated temporary locals (`$tN`):"),
  tableCaption("Lowering of operators not in the instruction set"),
  ...table(["Source", "Lowered form", "Instructions"], [
    ["a < b", "a < b", "LT"],
    ["a > b", "b < a", "store a, b in temps; LOAD b, LOAD a, LT"],
    ["a >= b", "1 − (a < b)", "PUSH 1, (a<b), SUB"],
    ["a == b", "1 − ((a<b) + (b<a))", "two LTs, ADD, SUB"],
    ["a != b", "(a<b) + (b<a)", "two LTs, ADD"],
    ["a % b", "a − (a / b) × b", "LOAD a, LOAD a, LOAD b, DIV, LOAD b, MUL, SUB"],
    ["!a", "a == 0", "PUSH 0, equality lowering"],
    ["-a", "0 − a", "PUSH 0, a, SUB"],
  ], [1600, 2600, 4826], { mono: [true, true, true] }),
  P("**Literals.** Object and array literals contain only constants, so they are built at compile time into the VM's object table; `a[i]` compiles to `PUSH base, i, ADD, LOADOBJ`. This is safe because the subset has no property or element writes."),
  H2("7.7 Complexity and trade-offs"),
  tableCaption("Cost of one property read (n = number of properties, k = cached entries ≤ 4)"),
  ...table(["Path", "Time per read", "Space", "Trade-off"], [
    ["Baseline scan", "O(n)", "none", "Simple and always correct; slow for wide objects"],
    ["IC hit, MONO", "O(1)", "1 entry per site", "Bookkeeping cost per read even when n is small"],
    ["IC hit, POLY", "O(k), k ≤ 4", "≤ 4 entries per site", "Short list stays cheap"],
    ["IC, MEGA", "O(1) hit / O(n) miss", "capacity entries per site", "Thrashes when shapes > capacity"],
    ["Tier 2", "O(1), one guard", "1 entry per site", "Only for hot MONO sites; deopt cost on failure"],
    ["Compiler", "O(tokens)", "O(code size)", "Single pass; no AST to optimise over"],
  ], [1600, 1900, 2000, 3526]),
];

const impl = [
  H1("8. Implementation Details"),
  H2("8.1 Code organisation"),
  tableCaption("Repository files and size (lines, including comments)"),
  ...table(["File", "Lines", "Purpose"], LOC.map((r) => [r.file, String(r.lines), r.purpose]), [2600, 900, 5526], { mono: [true, false, false] }),
  H2("8.2 Module walkthrough"),
  H3("VM and profiler (vm_ic_model.py, VM.run)"),
  P("A single `while pc < len(program)` loop with an `if/elif` chain on the opcode. JMP and JZ update `back_edge_counts` and `hot_flags` when the target is backward. GETFIELD delegates to the tier-2 table, the inline cache or the baseline scan depending on the mode flags passed to `run()`."),
  H3("Hidden classes and the inline cache"),
  P("`Shape.__new__` interns shapes by property-name tuple. `ic_getprop` implements Section 7.3; the MEGA table is an `OrderedDict` whose eviction order is FIFO by default and LRU when `MEGA_POLICY = \"LRU\"` (hits call `move_to_end`). Both parameters are module globals read at call time so the sweep scripts can vary them without changing code."),
  H3("Tier 2 and deoptimisation"),
  P("`VM.compiled` maps a pc to its guard and offset. `VM.deoptimize()` deletes the entry, calls `cache.__init__()` to hard-reset the site, records the post-reset state for IC5, and redoes the access through `ic_getprop`."),
  H3("Front end (jsc.py)"),
  P("`tokenize()` produces `(kind, text, line)` tuples. The `Compiler` class holds the token cursor, emitted code, the variable-to-slot map, array descriptors, the object table and a map from each GETFIELD pc to its source line, which `run_js.py` uses to report cache state per source line. Unsupported keywords (`function`, `return`, `true`, …) raise a `CompileError` with the line number."),
  H3("Evaluation harness"),
  P("`run_js.py` runs Node with a 10-second timeout, compiles the file, runs it in three modes, compares every line and prints per-site cache states. `test_all.py` is the regression suite (Section 9). `benchmark.py` repeats each timing five times and reports medians. `mega_tuning.py` and `threshold_sweep.py` are the parameter sweeps; `run_demo.command` is the one-click demo."),
  H2("8.3 Example: source to bytecode"),
  P("The loop body `total += items[i].x;` from `examples/deopt.js` compiles to the following bytecode; address 13 is the site that the cache and tier 2 optimise:"),
  ...code([
    " 4  LOAD 1        loop head: i",
    " 5  PUSH 20       items.length (compile-time constant)",
    " 6  LT            i < length ?",
    " 7  JZ 21         exit loop (target back-patched)",
    " 8  LOAD 0        total",
    " 9  PUSH 0        base address of items in the object table",
    "10  LOAD 1        i",
    "11  ADD           base + i",
    "12  LOADOBJ       items[i]",
    "13  GETFIELD x    .x   <- inline-cache / tier-2 site",
    "14  ADD           total + ...",
    "15  STORE 0       total = ...",
  ]),
  H2("8.4 Build and integration"),
  P("There is no build step: the project is pure Python 3 with no third-party dependencies. Integration is enforced by the test suite, which exercises the front end, VM, cache and tier 2 together on every example and compares the result with Node. The full procedure is in Appendix A."),
];

const testing = [
  H1("9. Testing Strategy and Test Cases"),
  H2("9.1 Strategy"),
  P("Testing has four layers, all run by `python3 test_all.py`:"),
  NUM("**Unit tests** — TC1–TC12 for the interpreter and IC1–IC5 for the inline cache, invalidation and deoptimisation. Each is a tiny program with a known answer.", "num2"),
  NUM("**Differential end-to-end tests** — each JavaScript example runs in three modes; all must equal Node's output line for line. This catches errors in the compiler and in every optimisation at once.", "num2"),
  NUM("**Negative and failure tests** — invalid programs must be rejected at compile time, or fail at run time, with a specific diagnostic.", "num2"),
  NUM("**Stress tests** — 50,000-access mono, poly and mega workloads with 0 mismatches between the cached and baseline runs.", "num2"),
  P("Boundary cases are covered by TC6 (division by zero), TC10 (equal operands for LT), TC12 (1,000-deep stack) and `examples/edge_cases.js` (zero-iteration loop, negative and large integers, four chained property reads, single-element array). Regression protection comes from running the whole suite after every change."),
  H2("9.2 Unit tests"),
  tableCaption("Interpreter unit tests (TC1–TC12)"),
  ...table(["Test", "Operation", "Expected", "Actual"], [
    ["TC1", "10 + 20", "30", "30 — PASS"], ["TC2", "20 − 5", "15", "15 — PASS"], ["TC3", "10 × 5", "50", "50 — PASS"],
    ["TC4", "20 ÷ 4", "5", "5 — PASS"], ["TC5", "(10 + 20) × 5", "150", "150 — PASS"], ["TC6", "10 ÷ 0", "VMError", "VMError — PASS"],
    ["TC7", "LOAD/STORE in 4 slots", "11, 22, 33, 44", "11, 22, 33, 44 — PASS"], ["TC8", "JMP over PRINT", "[1]", "[1] — PASS"],
    ["TC9", "JZ taken / not taken", "[7] and [42]", "PASS"], ["TC10", "LT on <, >, =", "1, 0, 0", "PASS"],
    ["TC11", "10-iteration loop, threshold 5", "address 2 flagged hot", "back-edges {2: 10} — PASS"], ["TC12", "1,000 PUSH then 1,000 POP", "empty stack", "empty — PASS"],
  ], [900, 3100, 2300, 2726]),
  tableCaption("Inline-cache unit tests (IC1–IC5)"),
  ...table(["Test", "Scenario", "Expected", "Actual"], [
    ["IC1", "1 shape, 1,000 reads", "MONO, 1 miss, 0 mismatches", "MONO, 1 miss, 0 mismatches"],
    ["IC2", "3 shapes round-robin", "POLY, 3 entries, 3 misses", "POLY, 3 entries, 3 misses"],
    ["IC3", "8 shapes round-robin", "MEGA, 0 mismatches", "MEGA, 0 hits / 1,000 misses, 0 mismatches"],
    ["IC4", "Shape mutated between runs", "version bump, 1 re-miss, correct value", "v0→v1; stale slot reads 2 (not 3); 1 re-miss"],
    ["IC5", "50 shape-A then 50 shape-B, tier 2", "1 deopt, reset to UNINIT, 0 mismatches", "2 compiles, 92 fast-path reads, 1 deopt, UNINIT"],
  ], [800, 2600, 2700, 2926]),
  H2("9.3 End-to-end tests against Node.js"),
  tableCaption("JavaScript programs: every mode compared with Node"),
  ...table(["Program", "What it exercises", "Lines compared", "Result"], testRows.filter((r) => r.group === "end-to-end").map((r) => [r.name, {
    "basics.js": "Precedence, if/else, while, for, %, objects, arrays",
    "deopt.js": "Shape change mid-loop; tier-2 deopt",
    "edge_cases.js": "Zero-iteration loop, negatives, 2^40, deep chains",
    "points_mega.js": "16 shapes at one site",
    "points_mono.js": "1 shape, 96,000 property reads",
    "points_poly.js": "3 shapes (field order permuted)",
    "points_wide.js": "1 shape, 32 fields",
  }[r.name] || "", r.expected.replace(" = Node", ""), "3 modes = Node"]), [2000, 3926, 1500, 1600]),
  H2("9.4 Invalid-input and failure tests"),
  tableCaption("Negative tests: expected diagnostic vs actual"),
  ...table(["Program", "Expected", "Actual diagnostic", "Result"], testRows.filter((r) => r.group === "invalid").map((r) => [r.name, r.expected, r.actual.replace(/^(compile|runtime) error: /, ""), r.result]),
    [2100, 2400, 3626, 900]),
  P("Three of these behave differently in JavaScript, which `run_js.py` reports explicitly: Node prints `Infinity` for `10 / 0` and `undefined` for a missing property, where our VM raises an error; and Node never terminates the infinite loop (it is stopped by a 10-second timeout), whereas our VM stops it at the step limit. These are documented in Section 11."),
  H2("9.5 Summary"),
  callout(`**Regression suite result: ${nPass} / ${testRows.length} checks pass** — ${testRows.filter((r) => r.group === "unit").length} unit, ${testRows.filter((r) => r.group === "end-to-end").length} end-to-end, ${testRows.filter((r) => r.group === "invalid").length} invalid-input and ${testRows.filter((r) => r.group === "stress").length} stress checks. The complete table is in Appendix D.`),
];

const results = [
  H1("10. Results and Evaluation"),
  H2("10.1 Benchmark setup"),
  P(`All timings were measured on one machine (${ENV.cpu}, ${ENV.mem}, ${ENV.os}, Python ${ENV.python}) by \`python3 benchmark.py\`, which runs each experiment ${B.reps} times and reports the median. Speedup is baseline time divided by optimised time; values above 1× are faster. Hit rates and mismatch counts are deterministic because the workloads use fixed seeds. The timings measure a Python model and therefore reflect algorithmic savings, not native performance.`),
  H2("10.2 Synthetic workloads (200-field objects)"),
  P("Each workload performs 100,000 GETFIELD reads at one site inside a bytecode loop. The target property sits after up to 200 other properties, so the uncached scan is expensive."),
  tableCaption(`Inline cache vs baseline, 100,000 reads (median of ${B.reps} runs)`),
  ...table(["Workload", "Hits / misses", "Hit rate", "Baseline (s)", "IC (s)", "Speedup", "Mismatches"], B.A.map((r) => [
    { mono: "Monomorphic (1 shape)", poly: "Polymorphic (3 shapes)", mega: "Megamorphic (16 shapes, 4 slots)" }[r.workload],
    `${r.hits.toLocaleString("en-US")} / ${r.misses.toLocaleString("en-US")}`, pct(r.hit_rate), r.t_base.toFixed(3), r.t_ic.toFixed(3), f2(r.speedup) + "×", String(r.mismatches)]),
    [2600, 1700, 900, 1100, 900, 900, 926], { align: [0, 2, 2, 2, 2, 2, 2].map((a) => (a ? AlignmentType.RIGHT : AlignmentType.LEFT)) }),
  ...figure("fig_synthetic.png", "Speedup of the inline cache on 200-field objects"),
  P(`**Interpretation.** A monomorphic hit replaces a scan over up to 200 names with one comparison, giving ${f2(A.mono.speedup)}×. Polymorphic sites check a list of three entries and some shapes have shorter scans, giving ${f2(A.poly.speedup)}×. The megamorphic site thrashes: 16 shapes compete for 4 slots, only ${pct(A.mega.hit_rate)} of reads hit, and the bookkeeping cancels the savings (${f2(A.mega.speedup)}×). Correctness is unaffected — 0 mismatches in every run.`),
  H2("10.3 Megamorphic cache tuning"),
  P("To close the Review 2 action item, the megamorphic table was swept over capacity (4, 8, 16 slots) and eviction policy (FIFO, LRU) on the same 16-shape workload."),
  tableCaption(`Megamorphic capacity × eviction policy (median of ${B.reps} runs)`),
  ...table(["Capacity", "Policy", "Hit rate", "Speedup", "Mismatches"], B.B.map((r) => [`${r.capacity} slots`, r.policy, pct(r.hit_rate), f2(r.speedup) + "×", String(r.mismatches)]),
    [1800, 1800, 1800, 1800, 1826]),
  ...figure("fig_mega.png", "Megamorphic cache: speedup by capacity and eviction policy"),
  P(`**Interpretation.** Hit rate tracks capacity ÷ number of shapes (≈25%, 50%, 100%), and FIFO and LRU reach the *same* hit rate at every capacity (${[4, 8, 16].map((c) => pct(M(c, "FIFO").hit_rate) + " vs " + pct(M(c, "LRU").hit_rate)).join("; ")}). With shapes arriving in random order every shape is equally likely to be needed next, so no eviction policy can choose a better victim: the policy does not change how often the cache misses. ${policyGap > 0.1 ? `The timing differences between the two policies (up to ${f2(policyGap)}×) are therefore not caused by hit rate; they come from run-to-run variation and the small extra cost of LRU's reordering.` : `Their timings differ by at most ${f2(policyGap)}×.`} With 16 slots the site never evicts, reaches 100% hits and is ${f2(M(16, "FIFO").speedup)}× (FIFO) / ${f2(M(16, "LRU").speedup)}× (LRU) faster than the baseline. The trade-off is memory per site, which is why production engines give each site a small cache backed by one large shared megamorphic cache.`),
  H2("10.4 JavaScript programs"),
  P("The JavaScript examples use small objects (6 fields) except `points_wide.js` (32 fields), which makes the cost of the cache itself visible."),
  tableCaption(`JavaScript programs: speedup over our baseline (median of ${B.reps} runs)`),
  ...table(["Program", "Hit rate", "IC", "IC + tier 2", "Fast-path reads"], B.C.map((r) => [r.program, pct(r.hit_rate), f2(r.ic_speedup) + "×", f2(r.t2_speedup) + "×", r.fast_path_reads.toLocaleString("en-US")]),
    [2400, 1500, 1500, 1800, 1826]),
  ...figure("fig_js.png", "Speedup of the cache and tier 2 on the JavaScript examples"),
  P(`**Interpretation.** With 6 fields the scan is so short that the cache's bookkeeping costs more than it saves: the cache alone is ${f2(C.points_mono.ic_speedup)}× on \`points_mono\` despite a 100% hit rate. Tier 2 removes the cache lookup for hot monomorphic sites and recovers the loss (${f2(C.points_mono.t2_speedup)}×). Polymorphic and megamorphic sites are never compiled (only MONO sites are), so tier 2 cannot help them. With 32 fields the scan is longer: the cache alone ${verdict(C.points_wide.ic_speedup)} (${f2(C.points_wide.ic_speedup)}×, against ${f2(C.points_mono.ic_speedup)}× with 6 fields) and tier 2 reaches ${f2(C.points_wide.t2_speedup)}×. The cache pays off in proportion to the cost of the lookup it replaces — the reason production engines compile cached accesses into machine code.`),
  H2("10.5 Hot-loop threshold sweep"),
  P("The threshold decides when a loop is hot and its monomorphic sites are compiled. The table and figure below show its effect."),
  tableCaption("Hot-threshold sweep: compiles, tier-2 reads, deopts, mismatches"),
  ...table(["Threshold", "IC5: compiles", "IC5: fast-path reads", "IC5: deopts", "Mono: fast-path reads", "Mismatches"],
    threshBlocks[0].rows.map((r, i) => [r[0], r[1], r[2], r[3], threshBlocks[1].rows[i][2], String(Number(r[4]) + Number(threshBlocks[1].rows[i][4]))]),
    [1300, 1400, 1700, 1300, 1800, 1526]),
  ...figure("fig_threshold.png", "Tier-2 coverage as a function of the hot-loop threshold"),
  P("**Interpretation.** A low threshold compiles earlier and serves more reads from tier 2. A high threshold has a subtler effect: on the IC5 workload, with a threshold of 50 or more the loop becomes hot only after shape B has appeared, so the site is already POLY and is *never* compiled — zero deopts, but also zero fast-path reads. Early compilation risks a deopt; late compilation risks missing the monomorphic window. The default of 5 compiles quickly while still letting the cache observe a few iterations. All 14 configurations produce 0 mismatches."),
  H2("10.6 Comparison with V8"),
  P(`\`v8_compare.js\` runs the same mono/poly/mega experiment in V8 (Node ${ENV.node}): 50 × 1,000,000 reads of \`o.x\` with 1, 3 and 16 shapes. ${B.D ? `The polymorphic case took ${f2(B.D.poly_vs_mono)}× and the megamorphic case ${f2(B.D.mega_vs_mono)}× the monomorphic time (median of 3 runs).` : ""} Absolute times are not comparable with our Python model, but the pattern is: V8 also handles one or a few shapes efficiently and slows down markedly at a megamorphic site — the behaviour our model predicts.`),
  H2("10.7 Overall assessment"),
  BUL(`**Correctness:** ${nPass}/${testRows.length} checks pass; zero mismatches in every benchmark, sweep and stress run; all seven JavaScript programs match V8 in all three modes.`),
  BUL(`**Performance:** large gains where the lookup is expensive (${f2(A.mono.speedup)}× on 200-field objects, ${f2(C.points_wide.t2_speedup)}× on 32-field objects with tier 2); the megamorphic weakness is fixed by capacity; small objects need tier 2 to break even.`),
];

const errors = [
  H1("11. Error Handling, Limitations and Known Issues"),
  H2("11.1 Error handling"),
  tableCaption("Errors detected and how they are reported"),
  ...table(["Condition", "Detected by", "Behaviour"], [
    ["Unexpected character, missing token", "Lexer / parser", "CompileError with line number, e.g. line 2: expected ')', got ';'"],
    ["Undeclared variable", "Parser", "CompileError: 'y' is not defined"],
    ["Unsupported construct (function, true, …)", "Parser", "CompileError: 'function' is not supported by this compiler"],
    ["Division by zero", "VM (DIV)", "VMError: division by zero"],
    ["Runaway loop", "VM step counter", "VMError: step limit exceeded (possible infinite loop)"],
    ["Missing property", "Baseline scan / IC miss", "property 'y' not found on object"],
    ["Unknown opcode", "VM dispatch", "VMError: unknown opcode"],
    ["Node does not terminate", "run_js.py", "Reported as NODE TIMEOUT after 10 s"],
  ], [3000, 2000, 4026]),
  H2("11.2 Unsupported features"),
  BUL("Strings, booleans (`true`/`false`), `null` and `undefined`."),
  BUL("Functions, closures, `return`, classes, `this`, prototypes and `new`."),
  BUL("Property writes (`p.x = 1`), element writes (`a[i] = 1`) and arrays of computed values; array literals must contain constants."),
  BUL("`break`, `continue`, `switch`, `do…while`, exceptions; `console.log` with more than one argument."),
  H2("11.3 Known behavioural differences from JavaScript"),
  tableCaption("Known differences from JavaScript semantics"),
  ...table(["Input", "JavaScript (Node)", "This engine", "Reason"], [
    ["10 / 0", "Infinity", "VMError", "Integer arithmetic only"],
    ["7 / 2", "3.5", "3", "DIV is integer division"],
    ["-7 % 3", "-1", "2", "% lowered via floor division"],
    ["console.log(3 < 5)", "true", "1", "Comparisons produce 1/0"],
    ["p.missing", "undefined", "error", "No undefined value"],
    ["a[100] (out of range)", "undefined", "IndexError / wrong element", "No bounds check on the object table"],
  ], [2100, 2000, 2200, 2726]),
  H2("11.4 Technical constraints"),
  BUL("**Python timing:** speedups reflect fewer operations per read, not machine-code speed; interpreter overhead dominates small programs."),
  BUL("**Tier 2 is a model:** the guarded load is a Python fast path, not generated machine code."),
  BUL("**Only monomorphic sites are compiled;** polymorphic sites stay in the cache."),
  BUL("**Shape registry is global** within a process, so shapes persist across tests; tests use distinct property names to avoid interference."),
  BUL("**Objects are immutable** after creation except through `mutate_shape`, which exists only to test invalidation."),
];

const contrib = [
  H1("12. Member-Wise Contribution"),
  P("Each member owned one module end to end — design, code and tests — and presents it in the demonstration and viva. The table below is the mandatory contribution matrix; the source locations listed can be inspected in the repository."),
  tableCaption("Final contribution matrix"),
  ...table(["Member", "Primary technical ownership", "Deliverable produced", "Evidence (files / tests)", "Integration / support", "Viva module"], [
    ["1 — Chilukuri Charith Reddy (24BCT0093)", "Stack VM and baseline interpreter", "Full 15-opcode interpreter; error handling (÷0, step limit)", "VM.run() in vm_ic_model.py; TC1–TC10, TC12", "System integration of VM with cache and tier 2", "VM, ISA, fetch–decode–execute"],
    ["2 — Vatsal Sharma (24BCE0334)", "Profiler and hot-code detection; differential testing", "Back-edge counters; configurable threshold", "back_edge_counts / hot_flags; TC11; threshold_sweep.py", "Differential-testing harness; timeline", "Hot loops, threshold trade-off"],
    ["3 — Mayan Manit (24BCE0506)", "Hidden classes and inline cache", "Shape/Obj; ICEntry; ic_getprop; MEGA table", "IC1–IC4; benchmark section A; mega_tuning.py", "Hit-rate and performance measurement", "Cache states, invalidation, hit rates"],
    ["4 — Ehsan Abdulkhader (24BCT0089)", "Tier 2, deoptimisation, JS front end, evaluation", "Guarded load + deopt; jsc.py; run_js.py; test_all.py; benchmark.py", "VM.deoptimize(); IC5; examples/, tests/invalid/; repository commits", "Repository, README, demo script, report and slides", "Tier 2, deopt, compiler, results"],
  ], [1500, 1500, 1700, 1700, 1400, 1226]),
  P("The contribution log in Appendix E lists the commits in the shared repository."),
];

const conclusion = [
  H1("13. Conclusion and Future Work"),
  H2("13.1 Objectives achieved"),
  P(`All seven objectives are met in the reference implementation. The engine executes bytecode correctly, detects hot loops, caches property offsets through four states, rejects stale entries after shape changes, compiles hot monomorphic reads to guarded loads and deoptimises safely, and runs real JavaScript programs whose output matches V8 in every mode. ${nPass} of ${testRows.length} regression checks pass and no benchmark, sweep or stress run produced a single mismatch.`),
  H2("13.2 Key learning"),
  BUL("**Correctness first.** A simple, trusted baseline and differential testing made every optimisation safe to build and easy to debug."),
  BUL("**Caches have a cost.** An inline cache pays off only when the lookup it replaces is expensive; on small objects compilation is needed to win."),
  BUL("**Capacity beats cleverness** for megamorphic sites: a better eviction policy did not help, more slots did."),
  BUL("**Speculation needs a safety net.** Deoptimisation lets compiled code assume aggressively without ever producing a wrong answer, and timing (the hot threshold) decides whether speculation pays off."),
  H2("13.3 Future work"),
  NUM("**Native code generation:** emit the tier-2 guard and load as machine code (for example with asmjit) and measure native speedups.", "num3"),
  NUM("**Polymorphic compilation:** compile POLY sites as a chain of guards instead of leaving them in the cache.", "num3"),
  NUM("**Shared megamorphic cache:** replace per-site MEGA tables with one global table, as V8 does, and measure the memory–hit-rate trade-off.", "num3"),
  NUM("**Larger language subset:** functions and calls (with call-site inline caches), strings, booleans and property writes with shape transitions.", "num3"),
  NUM("**Realistic workloads:** benchmark programs with mixed site behaviour and skewed shape distributions, where LRU may outperform FIFO.", "num3"),
  H2("13.4 Publication and further-development potential"),
  P("The project is well suited as an open educational artefact: a single-file, instrumented model of JIT techniques with a JavaScript front end and differential testing against V8. A short teaching paper or tool demonstration could report the measured trade-offs — cache cost on small objects, capacity versus policy, and the effect of the hot threshold on speculation — which are rarely shown quantitatively in teaching material."),
];

const refs = [
  H1("14. References"),
  ...[
    "A. V. Aho, M. S. Lam, R. Sethi and J. D. Ullman, *Compilers: Principles, Techniques, and Tools*, 2nd ed. Boston: Pearson/Addison-Wesley, 2006.",
    "L. P. Deutsch and A. M. Schiffman, “Efficient implementation of the Smalltalk-80 system,” in *Proc. 11th ACM Symposium on Principles of Programming Languages (POPL)*, 1984, pp. 297–302.",
    "C. Chambers, D. Ungar and E. Lee, “An efficient implementation of SELF, a dynamically-typed object-oriented language based on prototypes,” in *Proc. OOPSLA ’89*, 1989, pp. 49–70.",
    "U. Hölzle, C. Chambers and D. Ungar, “Optimizing dynamically-typed object-oriented languages with polymorphic inline caches,” in *Proc. ECOOP ’91*, LNCS 512, Springer, 1991, pp. 21–38.",
    "U. Hölzle, C. Chambers and D. Ungar, “Debugging optimized code with dynamic deoptimization,” in *Proc. ACM PLDI ’92*, 1992, pp. 32–43.",
    "J. Aycock, “A brief history of just-in-time,” *ACM Computing Surveys*, vol. 35, no. 2, pp. 97–113, 2003.",
    "A. Gal et al., “Trace-based just-in-time type specialization for dynamic languages,” in *Proc. ACM PLDI ’09*, 2009, pp. 465–478.",
    "T. Würthinger et al., “One VM to rule them all,” in *Proc. Onward! 2013*, ACM, 2013, pp. 187–204.",
    "V8 project, “Fast properties in V8,” V8 blog, 2017. [Online]. Available: https://v8.dev/blog/fast-properties",
    "Node.js project, *Node.js documentation*. [Online]. Available: https://nodejs.org/docs/",
    "Python Software Foundation, *The Python Language Reference* and *Python Standard Library* (collections.OrderedDict, re). [Online]. Available: https://docs.python.org/3/",
    "Ecma International, *ECMA-262: ECMAScript Language Specification*. [Online]. Available: https://tc39.es/ecma262/",
  ].map((t, i) => new Paragraph({ children: [new TextRun({ text: `[${i + 1}]  ` }), ...runs(t)], spacing: { after: 100, line: 276 }, indent: { left: 540, hanging: 540 } })),
  H3("Acknowledgement of tools"),
  P("Python and its standard library; Node.js/V8 as the reference engine; matplotlib for report figures; Microsoft PowerPoint and Word for the presentation and report; Git and GitHub for version control."),
];

const appendices = [
  H1("Appendix A: Installation and User Manual"),
  H2("A.1 Requirements"),
  BUL("Python 3.10 or newer (tested with " + ENV.python + "). No third-party packages."),
  BUL("Node.js (optional) for comparison with V8; without it, `run_js.py` compares our three modes with each other."),
  H2("A.2 Getting the code"),
  ...code(["gh repo clone eak560/a4-bytecode-jit-inline-cache", "cd a4-bytecode-jit-inline-cache"]),
  H2("A.3 Commands"),
  tableCaption("User commands"),
  ...table(["Command", "What it does", "Time"], [
    ["python3 test_all.py", "Full regression suite; exit status 0 if all pass", "≈ 25 s"],
    ["python3 vm_ic_model.py", "TC1–TC12, IC1–IC5 and the synthetic benchmark", "≈ 5 s"],
    ["python3 run_js.py examples/*.js", "Compile, run 3 ways, compare with Node", "≈ 2 s"],
    ["python3 run_js.py FILE --bytecode", "Also print the generated bytecode", "< 1 s"],
    ["python3 run_js.py FILE --max-steps N", "Lower the VM step limit", "—"],
    ["python3 benchmark.py [--reps N]", "Median-of-N timings for the report", "≈ 2 min"],
    ["python3 mega_tuning.py", "Megamorphic capacity × policy sweep", "≈ 15 s"],
    ["python3 threshold_sweep.py", "Hot-threshold sweep", "< 1 s"],
    ["python3 demo.py [--beat N]", "Paced presentation walkthrough", "—"],
    ["./run_demo.command", "One-click live demo (Enter between steps)", "≈ 1 min"],
  ], [3500, 4026, 1500], { mono: [true, false, false] }),
  H2("A.4 Writing your own program"),
  P("Create a `.js` file using the subset in Appendix C and run `python3 run_js.py myprog.js`. The report shows Node's output, whether each mode matches it, the timings, and the inline-cache state of every property-read site with its source line."),

  H1("Appendix B: Sample Runs"),
  H2("B.1 run_js.py on examples/deopt.js"),
  ...code(fs.readFileSync(path.join(HERE, "data", "deopt_run.txt"), "utf8").trimEnd().split("\n"), 13),
  H2("B.2 Invalid input"),
  ...code(fs.readFileSync(path.join(HERE, "data", "invalid_sample.txt"), "utf8").trimEnd().split("\n"), 13),

  H1("Appendix C: Grammar of the Supported JavaScript Subset"),
  ...code([
    "program     := statement*",
    "statement   := '{' statement* '}'",
    "             | ('let' | 'const' | 'var') declaration ';'?",
    "             | 'while' '(' expr ')' statement",
    "             | 'for' '(' [decl | assign] ';' expr ';' [assign] ')' statement",
    "             | 'if' '(' expr ')' statement ['else' statement]",
    "             | 'console' '.' 'log' '(' expr ')' ';'?",
    "             | assign ';'?",
    "declaration := IDENT '=' (arrayLit | expr)",
    "assign      := IDENT ('=' expr | '+=' expr | '-=' expr | '*=' expr | '++' | '--')",
    "expr        := additive [('<'|'>'|'<='|'>='|'=='|'!='|'==='|'!==') additive]",
    "additive    := term (('+' | '-') term)*",
    "term        := unary (('*' | '/' | '%') unary)*",
    "unary       := '-' unary | '!' unary | postfix",
    "postfix     := IDENT '.' 'length' | IDENT '[' expr ']' ('.' IDENT)*   (IDENT is an array)",
    "             | primary ('.' IDENT)*",
    "primary     := INT | IDENT | '(' expr ')' | objectLit",
    "objectLit   := '{' [IDENT ':' const (',' IDENT ':' const)* [',']] '}'",
    "arrayLit    := '[' [const (',' const)* [',']] ']'",
    "const       := ['-'] INT | objectLit",
    "",
    "Tokens:  INT = [0-9]+   IDENT = [A-Za-z_$][A-Za-z0-9_$]*   comments // and /* */",
  ]),

  H1("Appendix D: Complete Test Table"),
  tableCaption("All regression checks from test_all.py"),
  ...table(["#", "Group", "Test", "Expected", "Actual", "Result"], testRows.map((r, i) => [String(i + 1), r.group, r.name, r.expected, r.actual, r.result]),
    [500, 1100, 2000, 2000, 2526, 900], { fill: (r, i) => (i === 5 ? (r[5] === "PASS" ? "DDF1EF" : "F6D5D5") : undefined) }),

  H1("Appendix E: Contribution Log (Repository History)"),
  P("Commits in the shared repository at the time of writing (`git log`):"),
  ...code(GITLOG),
];

fillToc();
fs.writeFileSync(path.join(HERE, "data", "headings.json"), JSON.stringify(HEADINGS));

// ---------------- document ----------------
const doc = new Document({
  creator: "Team A4", title: "A4 Final Report — Bytecode JIT Compiler with Inline Caching",
  styles: {
    default: { document: { run: { font: FONT, size: 22, color: INK } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: HFONT, size: 34, bold: true, color: HEAD }, paragraph: { spacing: { before: 120, after: 240 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: HFONT, size: 26, bold: true, color: TEAL }, paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1, keepNext: true } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 23, bold: true, color: HEAD }, paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2, keepNext: true } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } },
        { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1080, hanging: 270 } } } }] },
      ...["num1", "num2", "num3"].map((ref) => ({ reference: ref, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] })),
    ],
  },
  sections: [
    { properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
      children: [...cover] },
    {
      properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1300, left: 1440, right: 1440 }, pageNumbers: { start: 1 } } },
      headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: "A4 · Bytecode JIT Compiler with Inline Caching · Final Report", size: 16, color: "8A8080" })] })] }) },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], size: 18, color: "8A8080" })] })] }) },
      children: [...declaration, ...toc, ...abstract, ...intro, ...objectives, ...background, ...reqs, ...design, ...algos, ...impl, ...testing, ...results, ...errors, ...contrib, ...conclusion, ...refs, ...appendices],
    },
  ],
});

Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("wrote", OUT, "figures", figN, "tables", tabN); });
