"""Figures for the A4 final report: 4 charts from measured data + 3 diagrams."""
import json
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fig")
os.makedirs(OUT, exist_ok=True)
D = json.load(open(os.path.join(HERE, "data", "bench.json")))

TEAL, ORANGE, INK, MUTED, GRID = "#00908A", "#C8742A", "#3A2E2F", "#6F6566", "#E4DEDE"
LIGHT_TEAL, LIGHT_TAN, DARK = "#DDF1EF", "#F6E7D8", "#4E3B3C"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titleweight": "bold", "axes.titlesize": 11, "axes.titlecolor": INK, "figure.dpi": 200,
})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, name), dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def ref_line(ax, horizontal=False):
    (ax.axvline if horizontal else ax.axhline)(1.0, color=INK, lw=1, ls="--", zorder=1)


# ---------- chart 1: synthetic workloads ----------
A = D["A"]
labels = {"mono": "Monomorphic\n(1 shape)", "poly": "Polymorphic\n(3 shapes)", "mega": "Megamorphic\n(16 shapes, 4 slots)"}
fig, ax = plt.subplots(figsize=(6.4, 2.8))
ys = range(len(A))[::-1]
vals = [r["speedup"] for r in A]
ax.barh(list(ys), vals, height=0.5, color=TEAL, zorder=2)
for y, r in zip(ys, A):
    ax.text(r["speedup"] + 0.03, y, f"{r['speedup']:.2f}×   (hit rate {r['hit_rate'] * 100:.1f}%)",
            va="center", color=INK, fontsize=9)
ax.set_yticks(list(ys), [labels[r["workload"]] for r in A])
ax.set_xlim(0, max(vals) * 1.55)
ref_line(ax, horizontal=True)
ax.set_xlabel("Speedup over baseline interpreter (× , higher is faster)")
ax.grid(axis="x", color=GRID, zorder=0)
ax.set_title("Inline cache vs baseline, 100,000 GETFIELD reads (200-field objects)", loc="left")
save(fig, "fig_synthetic.png")

# ---------- chart 2: JavaScript examples ----------
C = D["C"]
names = [r["program"].replace(".js", "") for r in C]
x = range(len(C))
w = 0.36
fig, ax = plt.subplots(figsize=(6.4, 3.0))
b1 = ax.bar([i - w / 2 for i in x], [r["ic_speedup"] for r in C], w, color=ORANGE, label="+ inline cache", zorder=2)
b2 = ax.bar([i + w / 2 + 0.02 for i in x], [r["t2_speedup"] for r in C], w, color=TEAL, label="+ inline cache + tier 2", zorder=2)
for bars in (b1, b2):
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.03, f"{b.get_height():.2f}×",
                ha="center", fontsize=8, color=INK)
ax.set_xticks(list(x), names)
ref_line(ax)
ax.set_ylabel("Speedup over baseline (×)")
ax.set_ylim(0, max(max(r["ic_speedup"], r["t2_speedup"]) for r in C) * 1.25)
ax.grid(axis="y", color=GRID, zorder=0)
ax.legend(frameon=False, fontsize=8, loc="upper left")
ax.set_title("JavaScript programs compiled by jsc.py (dashed line = no change)", loc="left")
save(fig, "fig_js.png")

# ---------- chart 3: megamorphic tuning ----------
B = D["B"]
caps = sorted({r["capacity"] for r in B})
fig, ax = plt.subplots(figsize=(6.4, 2.9))
for k, (policy, color) in enumerate((("FIFO", ORANGE), ("LRU", TEAL))):
    rows = [next(r for r in B if r["capacity"] == c and r["policy"] == policy) for c in caps]
    xs = [i + (k - 0.5) * 0.38 + (0.01 if k else 0) for i in range(len(caps))]
    bars = ax.bar(xs, [r["speedup"] for r in rows], 0.36, color=color, label=policy, zorder=2)
    for b, r in zip(bars, rows):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.03, f"{r['speedup']:.2f}×",
                ha="center", fontsize=8, color=INK)
ax.set_xticks(range(len(caps)), [f"{c} slots\n(hit rate {next(r for r in B if r['capacity'] == c)['hit_rate'] * 100:.0f}%)" for c in caps])
ref_line(ax)
ax.set_ylabel("Speedup over baseline (×)")
ax.set_ylim(0, max(r["speedup"] for r in B) * 1.3)
ax.grid(axis="y", color=GRID, zorder=0)
ax.legend(frameon=False, fontsize=8, loc="upper left", title="Eviction policy", title_fontsize=8)
ax.set_title("Megamorphic cache: capacity vs eviction policy (16 shapes)", loc="left")
save(fig, "fig_mega.png")

# ---------- chart 4: hot-threshold sweep ----------
txt = open(os.path.join(HERE, "data", "threshold.txt")).read().split("\n\n")
series = []
for block in txt:
    lines = [l for l in block.splitlines() if l.strip()]
    if not lines:
        continue
    pts = [tuple(int(v) for v in l.split()) for l in lines if re.match(r"\s+\d", l)]
    series.append((lines[0].split(":")[0], pts))
fig, ax = plt.subplots(figsize=(6.4, 2.9))
for (title, pts), color, label in zip(series, (ORANGE, TEAL),
                                      ("IC5 workload (shape A then shape B, 100 reads)", "Monomorphic workload (200 reads)")):
    ax.plot([p[0] for p in pts], [p[2] for p in pts], color=color, lw=2, marker="o", ms=5, label=label, zorder=3)
ax.set_xscale("log")
ax.set_xticks([1, 2, 5, 10, 25, 50, 100], ["1", "2", "5", "10", "25", "50", "100"])
ax.set_xlabel("Hot-loop threshold (back-edges before a loop counts as hot, log scale)")
ax.set_ylabel("Reads served by tier 2")
ax.grid(color=GRID, zorder=0)
ax.legend(frameon=False, fontsize=8, loc="lower left")
ax.set_title("Effect of the hot-loop threshold on tier-2 coverage", loc="left")
save(fig, "fig_threshold.png")


# ---------- diagrams ----------
def box(ax, x, y, w, h, text, fc=LIGHT_TEAL, tc=INK, bold=False, fs=9):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=fc, ec="none", zorder=2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=tc,
            fontweight="bold" if bold else "normal", zorder=3, linespacing=1.3)


def arrow(ax, p, q, text=None, color=MUTED, rad=0.0, tpos=0.5, toff=(0, 0.12)):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=12, color=color, lw=1.4,
                                 connectionstyle=f"arc3,rad={rad}", zorder=1))
    if text:
        ax.text(p[0] + (q[0] - p[0]) * tpos + toff[0], p[1] + (q[1] - p[1]) * tpos + toff[1], text,
                ha="center", fontsize=8, color=MUTED, style="italic")


# architecture
fig, ax = plt.subplots(figsize=(7.0, 4.2))
ax.set_xlim(0, 14); ax.set_ylim(0, 8.4); ax.axis("off")
box(ax, 0.2, 6.2, 2.6, 1.3, "JavaScript source\n(examples/*.js)", fc=LIGHT_TAN)
box(ax, 3.5, 6.2, 3.2, 1.3, "jsc.py front end\nlex → parse → emit\n+ lowering", fc=TEAL, tc="white", bold=True, fs=8.5)
box(ax, 7.4, 6.2, 2.6, 1.3, "Bytecode\n+ object table\n+ GETFIELD sites", fc=LIGHT_TAN)
box(ax, 10.8, 6.2, 3.0, 1.3, "Node.js / V8\nreference output", fc=LIGHT_TEAL)
arrow(ax, (2.8, 6.85), (3.5, 6.85)); arrow(ax, (6.7, 6.85), (7.4, 6.85))
arrow(ax, (1.5, 7.5), (12.3, 7.5), rad=-0.12, text="same file", tpos=0.5, toff=(0, 0.75))
ax.add_patch(FancyBboxPatch((0.2, 0.3), 9.8, 5.0, boxstyle="round,pad=0.02,rounding_size=0.12",
                            fc="#F7F5F5", ec=GRID, lw=1, zorder=0))
ax.text(0.45, 4.95, "vm_ic_model.py runtime", fontsize=9, fontweight="bold", color=INK)
box(ax, 0.5, 3.0, 2.9, 1.5, "Stack VM\nfetch–decode–execute\n13 + 2 opcodes", fc=LIGHT_TEAL)
box(ax, 3.8, 3.0, 2.9, 1.5, "Profiler\nback-edge counters\n→ hot loops", fc=LIGHT_TEAL)
box(ax, 0.5, 0.7, 2.9, 1.7, "Hidden classes\nShape (id, version)\nObj (shape, values)", fc=LIGHT_TEAL)
box(ax, 3.8, 0.7, 2.9, 1.7, "Inline cache\nUNINIT→MONO→\nPOLY→MEGA", fc=LIGHT_TEAL)
box(ax, 7.1, 0.7, 2.6, 3.8, "Tier 2\nguarded fast path\n\ndeoptimise on\nguard failure", fc=DARK, tc="white", bold=False)
arrow(ax, (8.7, 6.2), (5.3, 4.5), text="run", tpos=0.45, toff=(0.55, 0.15))
arrow(ax, (3.4, 3.75), (3.8, 3.75)); arrow(ax, (5.25, 3.0), (5.25, 2.4))
arrow(ax, (3.4, 1.55), (3.8, 1.55)); arrow(ax, (6.7, 1.55), (7.1, 1.55)); arrow(ax, (6.7, 3.75), (7.1, 3.75))
box(ax, 10.8, 2.3, 3.0, 2.2, "Compare\nevery printed line\n(3 modes vs Node)", fc=LIGHT_TAN)
arrow(ax, (12.3, 6.2), (12.3, 4.5)); arrow(ax, (9.7, 3.4), (10.8, 3.4), text="output", toff=(0, 0.15))
box(ax, 10.8, 0.4, 3.0, 1.3, "test_all.py · benchmark.py\nrun_js.py · demo.py", fc=LIGHT_TEAL, fs=8)
save(fig, "fig_architecture.png")

# IC state machine
fig, ax = plt.subplots(figsize=(7.0, 2.6))
ax.set_xlim(0, 14); ax.set_ylim(-0.2, 5); ax.axis("off")
states = [("UNINIT", "#BFE6F2", 1.4), ("MONO", TEAL, 5.0), ("POLY", ORANGE, 8.6), ("MEGA", DARK, 12.2)]
for name, color, cx in states:
    ax.add_patch(plt.Circle((cx, 3.0), 1.05, color=color, zorder=2))
    ax.text(cx, 3.0, name, ha="center", va="center", fontsize=9.5, fontweight="bold",
            color=INK if name == "UNINIT" else "white", zorder=3)
arrow(ax, (2.5, 3.0), (3.9, 3.0), "1st shape", toff=(0, 0.2))
arrow(ax, (6.1, 3.0), (7.5, 3.0), "2nd shape", toff=(0, 0.2))
arrow(ax, (9.7, 3.0), (11.1, 3.0), "5th shape", toff=(0, 0.2))
arrow(ax, (5.0, 1.9), (1.5, 1.9), rad=-0.45, text="tier-2 guard fails (compiled MONO site):\ndeopt, hard reset to UNINIT", tpos=0.5, toff=(0, -1.55))
for cx, t in [(1.4, "never executed"), (5.0, "1 entry\none compare"), (8.6, "2–4 entries\nlinear check"), (12.2, "bounded shared\ntable (4 slots)")]:
    ax.text(cx, 4.45, t, ha="center", va="center", fontsize=8, color=MUTED)
save(fig, "fig_states.png")

# GETFIELD paths
fig, ax = plt.subplots(figsize=(7.0, 3.6))
ax.set_xlim(0, 14); ax.set_ylim(0, 7.2); ax.axis("off")
box(ax, 5.0, 6.0, 4.0, 0.9, "GETFIELD x  at site pc", fc=LIGHT_TAN, bold=True)
box(ax, 5.0, 4.4, 4.0, 1.0, "pc compiled (tier 2)?", fc="#F2D9BF")
box(ax, 0.3, 2.4, 4.0, 1.2, "Guard: shape id and\nversion match?", fc="#F2D9BF")
box(ax, 0.3, 0.3, 4.0, 1.2, "Direct load values[k]\n(no lookup)", fc=TEAL, tc="white", bold=True)
box(ax, 5.0, 2.4, 4.0, 1.2, "Deoptimise: drop code,\nreset IC → UNINIT", fc=DARK, tc="white")
box(ax, 9.7, 2.4, 4.0, 1.2, "IC lookup (ic_getprop)\nhit: values[k] · miss: scan", fc=LIGHT_TEAL)
box(ax, 9.7, 0.3, 4.0, 1.2, "Loop hot and site MONO?\n→ compile guarded load", fc=LIGHT_TEAL)
arrow(ax, (7.0, 6.0), (7.0, 5.4))
arrow(ax, (5.0, 4.9), (2.3, 3.6), "yes", toff=(-0.3, 0.1))
arrow(ax, (9.0, 4.9), (11.7, 3.6), "no", toff=(0.3, 0.1))
arrow(ax, (2.3, 2.4), (2.3, 1.5), "yes", toff=(0.35, -0.05))
arrow(ax, (4.3, 3.0), (5.0, 3.0), "no", toff=(0, 0.12))
arrow(ax, (9.0, 3.0), (9.7, 3.0))
arrow(ax, (11.7, 2.4), (11.7, 1.5))
save(fig, "fig_getfield.png")
print("figures:", sorted(os.listdir(OUT)))
