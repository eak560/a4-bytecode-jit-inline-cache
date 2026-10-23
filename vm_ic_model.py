"""
Bytecode VM + Inline Cache reference model (Project A4)
=========================================================
This is a real, runnable Python reference implementation of:
  (A) the stack-based bytecode VM + baseline interpreter (TC1-TC12), and
  (B) the inline-cache state machine (UNINIT -> MONO -> POLY -> MEGA),
      with version-checked lazy invalidation on shape mutation and a
      minimal tier-2 guarded fast path that deoptimises on guard failure
      (IC1-IC5), benchmarked against the same baseline on monomorphic,
      polymorphic and megamorphic property-access workloads.

Every number this script prints is measured on this run, not invented.
Re-run it any time -- e.g. after changing N_ITERS, shape counts, or the
MEGA cache capacity -- and the numbers below will change accordingly.
"""

import random
import time
from collections import OrderedDict

# ============================================================
# SECTION A: Bytecode VM + baseline interpreter
# ============================================================

class VMError(Exception):
    pass


class VM:
    """Stack-based bytecode VM implementing the Review 1 instruction set,
    plus GETFIELD (property access) used to exercise inline caching."""

    def __init__(self, n_locals=8, hot_threshold=5, objects=None):
        self.locals = [0] * n_locals
        self.hot_threshold = hot_threshold
        self.objects = objects or []
        self.compiled = {}  # pc -> (shape_id, version, offset): tier-2 guarded fast paths

    def deoptimize(self, pc, ic_caches, obj, name, stats):
        """Tier-2 guard failed: throw away the compiled fast path, hard-reset
        the call site's inline cache to UNINIT, and redo the access through
        the interpreter + IC path so the result is still correct."""
        del self.compiled[pc]
        cache = ic_caches[pc]
        cache.__init__()  # hard reset -> UNINIT, all entries dropped
        stats["deopts"] += 1
        stats["deopt_states"].append(cache.state)
        return ic_getprop(cache, obj, name, stats)

    def run(self, program, ic_mode=False, ic_caches=None, stats=None, max_steps=2_000_000,
            tier2=False):
        stack = []
        output = []
        back_edge_counts = {}
        hot_flags = set()
        pc = 0
        steps = 0
        MAX_STEPS = max_steps  # guard against runaway programs

        while pc < len(program):
            steps += 1
            if steps > MAX_STEPS:
                raise VMError("step limit exceeded (possible infinite loop)")

            op, arg = program[pc]

            if op == "PUSH":
                stack.append(arg)
                pc += 1
            elif op == "POP":
                stack.pop()
                pc += 1
            elif op == "ADD":
                b = stack.pop(); a = stack.pop(); stack.append(a + b)
                pc += 1
            elif op == "SUB":
                b = stack.pop(); a = stack.pop(); stack.append(a - b)
                pc += 1
            elif op == "MUL":
                b = stack.pop(); a = stack.pop(); stack.append(a * b)
                pc += 1
            elif op == "DIV":
                b = stack.pop(); a = stack.pop()
                if b == 0:
                    raise VMError("division by zero")
                stack.append(a // b)
                pc += 1
            elif op == "LOAD":
                stack.append(self.locals[arg])
                pc += 1
            elif op == "LOADOBJ":
                idx = stack.pop()
                stack.append(self.objects[idx])
                pc += 1
            elif op == "STORE":
                self.locals[arg] = stack.pop()
                pc += 1
            elif op == "JMP":
                if arg <= pc:  # backward jump -> loop back-edge
                    back_edge_counts[arg] = back_edge_counts.get(arg, 0) + 1
                    if back_edge_counts[arg] >= self.hot_threshold:
                        hot_flags.add(arg)
                pc = arg
            elif op == "JZ":
                v = stack.pop()
                if v == 0:
                    if arg <= pc:
                        back_edge_counts[arg] = back_edge_counts.get(arg, 0) + 1
                        if back_edge_counts[arg] >= self.hot_threshold:
                            hot_flags.add(arg)
                    pc = arg
                else:
                    pc += 1
            elif op == "LT":
                b = stack.pop(); a = stack.pop(); stack.append(1 if a < b else 0)
                pc += 1
            elif op == "PRINT":
                output.append(stack[-1])
                pc += 1
            elif op == "GETFIELD":
                obj = stack.pop()
                name = arg
                if pc in self.compiled:
                    # tier-2: guarded direct load, no IC lookup at all
                    sid, version, offset = self.compiled[pc]
                    if obj.shape.id == sid and obj.shape.version == version:
                        stats["tier2_hits"] += 1
                        value = obj.values[offset]
                    else:
                        value = self.deoptimize(pc, ic_caches, obj, name, stats)
                elif ic_mode:
                    cache = ic_caches.setdefault(pc, ICEntry())
                    value = ic_getprop(cache, obj, name, stats)
                    # compile a monomorphic site once a loop has gone hot
                    if tier2 and hot_flags and cache.state == "MONO":
                        self.compiled[pc] = cache.entries[0]
                        stats["compiles"] += 1
                else:
                    value = baseline_getprop(obj, name)
                stack.append(value)
                pc += 1
            elif op == "HALT":
                break
            else:
                raise VMError(f"unknown opcode {op}")

        return {"output": output, "stack": stack, "hot_flags": hot_flags,
                "back_edge_counts": back_edge_counts}


def run_tests():
    print("=" * 72)
    print("SECTION A -- Baseline interpreter correctness (TC1-TC12)")
    print("=" * 72)

    results = []

    def check(name, cond, detail=""):
        status = "PASS" if cond else "FAIL"
        results.append((name, status))
        print(f"  [{status}] {name}" + (f"  -- {detail}" if detail else ""))

    # TC1-TC5: arithmetic
    vm = VM()
    r = vm.run([("PUSH", 10), ("PUSH", 20), ("ADD", None), ("PRINT", None), ("HALT", None)])
    check("TC1 addition (10+20=30)", r["output"] == [30], f"got {r['output']}")

    vm = VM()
    r = vm.run([("PUSH", 20), ("PUSH", 5), ("SUB", None), ("PRINT", None), ("HALT", None)])
    check("TC2 subtraction (20-5=15)", r["output"] == [15], f"got {r['output']}")

    vm = VM()
    r = vm.run([("PUSH", 10), ("PUSH", 5), ("MUL", None), ("PRINT", None), ("HALT", None)])
    check("TC3 multiplication (10*5=50)", r["output"] == [50], f"got {r['output']}")

    vm = VM()
    r = vm.run([("PUSH", 20), ("PUSH", 4), ("DIV", None), ("PRINT", None), ("HALT", None)])
    check("TC4 division (20/4=5)", r["output"] == [5], f"got {r['output']}")

    vm = VM()
    r = vm.run([("PUSH", 10), ("PUSH", 20), ("ADD", None), ("PUSH", 5), ("MUL", None),
                ("PRINT", None), ("HALT", None)])
    check("TC5 sequencing ((10+20)*5=150)", r["output"] == [150], f"got {r['output']}")

    # TC6: divide by zero
    vm = VM()
    try:
        vm.run([("PUSH", 10), ("PUSH", 0), ("DIV", None), ("HALT", None)])
        check("TC6 divide-by-zero raises", False, "no exception raised")
    except VMError:
        check("TC6 divide-by-zero raises", True)

    # TC7: LOAD/STORE round trip across 4 local slots
    vm = VM(n_locals=4)
    prog = []
    for i, v in enumerate([11, 22, 33, 44]):
        prog += [("PUSH", v), ("STORE", i)]
    for i in range(4):
        prog += [("LOAD", i), ("PRINT", None)]
    prog += [("HALT", None)]
    r = vm.run(prog)
    check("TC7 LOAD/STORE round trip", r["output"] == [11, 22, 33, 44], f"got {r['output']}")

    # TC8: JMP over a PRINT
    vm = VM()
    prog = [("PUSH", 99), ("JMP", 3), ("PRINT", None), ("PUSH", 1), ("PRINT", None), ("HALT", None)]
    r = vm.run(prog)
    check("TC8 unconditional jump skips PRINT", r["output"] == [1], f"got {r['output']}")

    # TC9: JZ taken / not-taken
    vm = VM()
    prog = [("PUSH", 0), ("JZ", 3), ("PRINT", None), ("PUSH", 7), ("PRINT", None), ("HALT", None)]
    r = vm.run(prog)
    taken_ok = r["output"] == [7]
    vm = VM()
    prog = [("PUSH", 1), ("JZ", 4), ("PUSH", 42), ("PRINT", None), ("HALT", None)]
    r2 = vm.run(prog)
    check("TC9 JZ taken and not-taken", taken_ok and r2["output"] == [42])

    # TC10: LT comparisons
    vm = VM()
    r = vm.run([("PUSH", 3), ("PUSH", 5), ("LT", None), ("PRINT", None), ("HALT", None)])
    a = r["output"] == [1]
    vm = VM()
    r = vm.run([("PUSH", 5), ("PUSH", 3), ("LT", None), ("PRINT", None), ("HALT", None)])
    b = r["output"] == [0]
    vm = VM()
    r = vm.run([("PUSH", 5), ("PUSH", 5), ("LT", None), ("PRINT", None), ("HALT", None)])
    c = r["output"] == [0]
    check("TC10 LT (less/greater/equal)", a and b and c)

    # TC11: loop with back-edge counter reaching hot threshold
    vm = VM(hot_threshold=5)
    prog = [
        ("PUSH", 0), ("STORE", 0),               # i = 0
        ("LOAD", 0), ("PUSH", 10), ("LT", None),  # 2: i < 10
        ("JZ", 11),                                # exit loop if false -> HALT at index 11
        ("LOAD", 0), ("PUSH", 1), ("ADD", None), ("STORE", 0),  # i += 1
        ("JMP", 2),                                # 10: back-edge to loop head (index 2)
        ("HALT", None),                            # 11
    ]
    r = vm.run(prog)
    check("TC11 hot-path flag raised at back-edge threshold",
          2 in r["hot_flags"], f"back_edge_counts={r['back_edge_counts']}")

    # TC12: nested PUSH/POP stack depth stress
    vm = VM()
    prog = [("PUSH", i) for i in range(1000)] + [("POP", None) for _ in range(1000)] + [("HALT", None)]
    r = vm.run(prog)
    check("TC12 stack depth stress (1000 push/pop, no over/underflow)", r["stack"] == [])

    n_pass = sum(1 for _, s in results if s == "PASS")
    print(f"\n  Result: {n_pass} / {len(results)} passing\n")
    return results


# ============================================================
# SECTION B: Inline cache model
# ============================================================

class Shape:
    _registry = {}
    _next_id = [0]

    def __new__(cls, prop_names):
        key = tuple(prop_names)
        if key in cls._registry:
            return cls._registry[key]
        obj = object.__new__(cls)
        obj.id = cls._next_id[0]
        cls._next_id[0] += 1
        obj.props = list(prop_names)
        obj.version = 0  # bumped on in-place mutation -> invalidates cached offsets
        cls._registry[key] = obj
        return obj


class Obj:
    __slots__ = ("shape", "values")

    def __init__(self, shape, values):
        self.shape = shape
        self.values = values


def make_object(prop_values: dict):
    props = list(prop_values.keys())
    shape = Shape(props)
    values = [prop_values[p] for p in props]
    return Obj(shape, values)


def mutate_shape(shape, index, name, objects, default=0):
    """Insert a new property into an existing shape IN PLACE (e.g. a class
    gaining a field after objects already exist). Every object of that shape
    is re-laid-out, so any offset cached before the mutation may now point
    at the wrong slot -- bumping shape.version is what lets the inline cache
    notice that lazily, on its next access, instead of reading a stale slot."""
    old_key = tuple(shape.props)
    for obj in objects:
        if obj.shape is shape:
            obj.values.insert(index, default)
    shape.props.insert(index, name)
    shape.version += 1
    Shape._registry.pop(old_key, None)
    Shape._registry.setdefault(tuple(shape.props), shape)


def baseline_getprop(obj, name):
    """Naive dynamic lookup: linear scan of property names, as a
    property-bag object with no hidden-class / inline-cache optimisation
    would have to do on every single access."""
    for i, p in enumerate(obj.shape.props):
        if p == name:
            return obj.values[i]
    raise AttributeError(name)


def _slow_offset(obj, name):
    for i, p in enumerate(obj.shape.props):
        if p == name:
            return i
    raise AttributeError(name)


MEGA_CACHE_CAPACITY = 4  # bounded megamorphic table -> models a real,
                         # size-limited shared cache rather than an
                         # unbounded dict, so MEGA sites can still miss


class ICEntry:
    __slots__ = ("state", "entries", "mega_table")

    def __init__(self):
        self.state = "UNINIT"
        self.entries = []                # [(shape_id, version, offset), ...] for MONO/POLY
        self.mega_table = OrderedDict()  # shape_id -> (version, offset), FIFO-evicted, for MEGA


def new_stats():
    return {"hits": 0, "misses": 0, "compiles": 0, "tier2_hits": 0,
            "deopts": 0, "deopt_states": []}


def ic_getprop(cache: ICEntry, obj: Obj, name: str, stats: dict):
    # An entry only counts as a hit if BOTH the shape id and the shape
    # version match: a version mismatch means the shape was mutated after
    # the offset was cached, so the cached offset is stale (lazy invalidation).
    shape = obj.shape

    if cache.state == "MEGA":
        entry = cache.mega_table.get(shape.id)
        if entry is not None and entry[0] == shape.version:
            stats["hits"] += 1
            return obj.values[entry[1]]
        stats["misses"] += 1
        offset = _slow_offset(obj, name)
        cache.mega_table[shape.id] = (shape.version, offset)
        if len(cache.mega_table) > MEGA_CACHE_CAPACITY:
            cache.mega_table.popitem(last=False)  # evict oldest
        return obj.values[offset]

    for sid, version, offset in cache.entries:
        if sid == shape.id and version == shape.version:
            stats["hits"] += 1
            return obj.values[offset]

    stats["misses"] += 1
    offset = _slow_offset(obj, name)
    # drop any stale entry for this shape so a mutated shape replaces its
    # old entry instead of occupying a second slot
    cache.entries = [e for e in cache.entries if e[0] != shape.id]
    cache.entries.append((shape.id, shape.version, offset))

    if len(cache.entries) == 1:
        cache.state = "MONO"
    elif len(cache.entries) <= 4:
        cache.state = "POLY"
    else:
        cache.mega_table = OrderedDict((sid, (ver, off)) for sid, ver, off in cache.entries)
        while len(cache.mega_table) > MEGA_CACHE_CAPACITY:
            cache.mega_table.popitem(last=False)
        cache.entries = []
        cache.state = "MEGA"

    return obj.values[offset]


# ---------- workload generation ----------

N_DUMMY_PROPS = 200  # target property 'x' sits after this many others in
                      # the worst case, so an uncached linear-scan lookup
                      # has a real, measurable cost relative to a cached
                      # O(1)/O(k<=4) lookup -- this models a realistic
                      # object with many fields (e.g. a DOM node or a
                      # wide record type), not an unfair benchmark

def shape_with_x_at(index):
    props = [f"f{i}" for i in range(N_DUMMY_PROPS)]
    props.insert(index, "x")
    values = {p: i for i, p in enumerate(props)}
    values["x"] = 12345
    return props, values


def build_workload(kind, n, seed):
    rng = random.Random(seed)
    objs = []
    if kind == "mono":
        props, values = shape_with_x_at(N_DUMMY_PROPS)  # x last -> worst-case scan
        for _ in range(n):
            objs.append(make_object(dict(values)))
    elif kind == "poly":
        variants = [shape_with_x_at(idx) for idx in (20, 90, 180)]  # 3 distinct shapes
        for _ in range(n):
            props, values = rng.choice(variants)
            objs.append(make_object(dict(values)))
    elif kind == "mega":
        variants = [shape_with_x_at(idx) for idx in range(0, N_DUMMY_PROPS + 1, 13)]  # 16 shapes
        for _ in range(n):
            props, values = rng.choice(variants)
            objs.append(make_object(dict(values)))
    else:
        raise ValueError(kind)
    return objs


def build_loop_program(n):
    """A real hot loop: GETFIELD sits at ONE fixed bytecode address (index 6)
    and is executed n times as the loop counter walks the object array --
    this is what makes a per-call-site inline cache meaningful. Locals:
    slot 0 = loop counter i."""
    prog = [
        ("PUSH", 0), ("STORE", 0),                       # 0: i=0 ... STORE at 1
        ("LOAD", 0),                                      # 2: loop head
        ("PUSH", n),                                       # 3
        ("LT", None),                                       # 4
        ("JZ", 16),                                          # 5: exit -> HALT at 16
        ("LOAD", 0),                                          # 6
        ("LOADOBJ", None),                                     # 7
        ("GETFIELD", "x"),                                      # 8: fixed call site
        ("PRINT", None),                                        # 9
        ("POP", None),                                           # 10
        ("LOAD", 0),                                              # 11
        ("PUSH", 1),
        ("ADD", None),
        ("STORE", 0),
        ("JMP", 2),
        ("HALT", None),
    ]
    return prog


def run_workload(kind, n, seed):
    objs = build_workload(kind, n, seed)
    program = build_loop_program(n)
    steps_budget = n * 30 + 1000

    # --- baseline run ---
    vm = VM(objects=objs)
    t0 = time.perf_counter()
    r_base = vm.run(program, ic_mode=False, max_steps=steps_budget)
    t_base = time.perf_counter() - t0

    # --- cached run (same objects, same order -> differential test) ---
    vm2 = VM(objects=objs)
    ic_caches = {}
    stats = new_stats()
    t0 = time.perf_counter()
    r_cached = vm2.run(program, ic_mode=True, ic_caches=ic_caches, stats=stats, max_steps=steps_budget)
    t_cached = time.perf_counter() - t0

    mismatches = sum(1 for a, b in zip(r_base["output"], r_cached["output"]) if a != b)
    hit_rate = stats["hits"] / (stats["hits"] + stats["misses"]) if (stats["hits"] + stats["misses"]) else 0.0
    speedup = t_base / t_cached if t_cached > 0 else float("inf")

    return {
        "n": n, "t_base": t_base, "t_cached": t_cached, "speedup": speedup,
        "hits": stats["hits"], "misses": stats["misses"], "hit_rate": hit_rate,
        "mismatches": mismatches,
    }


GETFIELD_PC = 8  # address of the GETFIELD call site in build_loop_program


def small_objects(x_positions, n):
    """n objects cycling round-robin through one small shape per entry in
    x_positions ('x' inserted at that index among 8 filler props). Uses its
    own 'p*' prop names so these shapes never collide with the benchmark's."""
    variants = []
    for idx in x_positions:
        props = [f"p{i}" for i in range(8)]
        props.insert(idx, "x")
        variants.append({p: (100 + idx if p == "x" else i) for i, p in enumerate(props)})
    return [make_object(dict(variants[i % len(variants)])) for i in range(n)]


def run_ic_tests():
    print("=" * 72)
    print("SECTION B1 -- Inline cache state machine, invalidation, deopt (IC1-IC5)")
    print("=" * 72)

    results = []

    def check(name, cond, detail=""):
        status = "PASS" if cond else "FAIL"
        results.append((name, status))
        print(f"  [{status}] {name}" + (f"  -- {detail}" if detail else ""))

    def run_both(objs, tier2=False):
        """Run the same loop with and without the IC; return what the tests need."""
        prog = build_loop_program(len(objs))
        base = VM(objects=objs).run(prog)
        caches, stats = {}, new_stats()
        cached = VM(objects=objs).run(prog, ic_mode=True, ic_caches=caches, stats=stats,
                                      tier2=tier2)
        mismatches = sum(1 for a, b in zip(base["output"], cached["output"]) if a != b)
        return caches[GETFIELD_PC], stats, mismatches, base["output"], cached["output"]

    # IC1: one shape -> MONO
    cache, stats, mm, _, _ = run_both(small_objects([3], 1000))
    check("IC1 single shape reaches MONO, no mismatch",
          cache.state == "MONO" and mm == 0 and stats["misses"] == 1,
          f"state={cache.state}, misses={stats['misses']}, mismatches={mm}")

    # IC2: three shapes round-robin -> POLY
    cache, stats, mm, _, _ = run_both(small_objects([0, 4, 8], 1000))
    check("IC2 three shapes reach POLY, no mismatch",
          cache.state == "POLY" and len(cache.entries) == 3 and mm == 0 and stats["misses"] == 3,
          f"state={cache.state}, entries={len(cache.entries)}, misses={stats['misses']}, mismatches={mm}")

    # IC3: eight shapes round-robin -> MEGA (capacity 4, so FIFO thrashes)
    cache, stats, mm, _, _ = run_both(small_objects(range(8), 1000))
    check("IC3 eight shapes reach MEGA, no mismatch",
          cache.state == "MEGA" and mm == 0,
          f"state={cache.state}, hits={stats['hits']}, misses={stats['misses']}, mismatches={mm}")

    # IC4: shape mutated between two runs that share the same cache
    objs = [make_object({"a": 1, "b": 2, "x": 3}) for _ in range(50)]
    shape = objs[0].shape
    prog = build_loop_program(len(objs))
    caches, stats = {}, new_stats()
    VM(objects=objs).run(prog, ic_mode=True, ic_caches=caches, stats=stats)
    cache = caches[GETFIELD_PC]
    warmed = cache.state == "MONO"
    _, _, stale_offset = cache.entries[0]
    old_version = shape.version

    mutate_shape(shape, 0, "new_field", objs)  # x moves from offset 2 to offset 3
    stale_read = objs[0].values[stale_offset]   # what a cache WITHOUT a version check would return
    misses_before = stats["misses"]
    r = VM(objects=objs).run(prog, ic_mode=True, ic_caches=caches, stats=stats)
    base = VM(objects=objs).run(prog)
    new_misses = stats["misses"] - misses_before
    check("IC4 shape mutation: version bump invalidates stale entry",
          warmed and stale_read != 3 and shape.version == old_version + 1
          and r["output"] == base["output"] == [3] * len(objs)
          and new_misses == 1 and cache.state == "MONO" and cache.entries[0][1] == shape.version,
          f"version {old_version}->{shape.version}, stale slot would read {stale_read} (not 3), "
          f"re-misses after mutation={new_misses}")

    # IC5: tier-2 compiled path deopts when a new shape arrives mid-loop
    shape_a = [make_object({"a": 1, "x": 10}) for _ in range(50)]  # x at offset 1
    shape_b = [make_object({"x": 20, "a": 1}) for _ in range(50)]  # x at offset 0
    cache, stats, mm, base_out, _ = run_both(shape_a + shape_b, tier2=True)
    b_id = shape_b[0].shape.id
    check("IC5 deopt on tier-2 guard failure hard-resets cache to UNINIT",
          stats["deopts"] == 1 and stats["deopt_states"] == ["UNINIT"]
          and cache.state == "MONO" and [e[0] for e in cache.entries] == [b_id]
          and stats["tier2_hits"] > 0 and mm == 0,
          f"compiles={stats['compiles']}, tier2 hits={stats['tier2_hits']}, "
          f"deopts={stats['deopts']}, state after deopt={stats['deopt_states']}, "
          f"final state={cache.state} holding {'only shape B' if [e[0] for e in cache.entries] == [b_id] else 'stale shape A too'}, "
          f"mismatches={mm}")

    n_pass = sum(1 for _, s in results if s == "PASS")
    print(f"\n  Result: {n_pass} / {len(results)} passing\n")
    return results


def run_ic_benchmarks():
    print("=" * 72)
    print("SECTION B -- Inline cache: differential testing, hit rate, timing")
    print("=" * 72)

    N = 100_000
    rows = []
    for kind, label in [("mono", "Monomorphic (1 shape)"),
                         ("poly", "Polymorphic (3 shapes)"),
                         ("mega", "Megamorphic (16 shapes, capacity 4)")]:
        res = run_workload(kind, N, seed=42)
        rows.append((label, res))
        print(f"\n{label}  (n={N:,} GETFIELD accesses)")
        print(f"  differential mismatches vs baseline : {res['mismatches']}")
        print(f"  cache hits / misses                 : {res['hits']:,} / {res['misses']:,}")
        print(f"  measured hit rate                   : {res['hit_rate']*100:.1f}%")
        print(f"  baseline time                       : {res['t_base']:.4f} s")
        print(f"  interpreter+IC time                 : {res['t_cached']:.4f} s")
        print(f"  measured speedup                    : {res['speedup']:.2f}x")

    print("\n" + "=" * 72)
    print("SUMMARY TABLE (paste into the report)")
    print("=" * 72)
    print(f"{'Workload':<38}{'Hit rate':>10}{'Baseline (s)':>15}{'IC (s)':>10}{'Speedup':>10}")
    for label, res in rows:
        print(f"{label:<38}{res['hit_rate']*100:>9.1f}%{res['t_base']:>15.4f}"
              f"{res['t_cached']:>10.4f}{res['speedup']:>9.2f}x")
    total_mismatches = sum(r["mismatches"] for _, r in rows)
    print(f"\nTotal differential-testing mismatches across all workloads: {total_mismatches}")
    return rows


if __name__ == "__main__":
    test_results = run_tests()
    ic_test_results = run_ic_tests()
    bench_rows = run_ic_benchmarks()
