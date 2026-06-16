#!/usr/bin/env python3
# =============================================================================
# nest_compare.py — beNNch-style weak-scaling comparison of NEST HPC sweeps
#                   across an arbitrary number of software stacks.
#
# Stacks (portability spectrum):
#   1. ml     — bare-metal site module-load (ParaStationMPI)        [least portable]
#   2. cvmfs  — portable container, links EESSI stack from /cvmfs   [portable]
#   3. hp     — highly portable, fully self-contained container     [most portable]
#
# Each input CSV has columns:
#   tag,nodes,jobid,vps,procs,threads,neurons,network_size,
#   connections_global,build_nodes,build_edges,presim,sim,mem_after_sim,rate
#
# Usage: edit STACKS below, then `python3 nest_compare.py`.
# Missing CSVs are skipped. Missing INTERIOR node points are extrapolated from
# the reference stack and clearly marked; missing endpoints are left blank.
# =============================================================================
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# ---- CONFIG -----------------------------------------------------------------
UPLOADS = "/mnt/user-data/uploads"
OUT     = "/mnt/user-data/outputs"

STACKS = [
    {"short": "ml",       "label": "Bare-metal (module load)",
     "csv": "/home/claude/nest_ml_sweep_results.csv",       "color": "#3557a3"},
    {"short": "cvmfs",    "label": "Portable container (CVMFS/EESSI)",
     "csv": "/home/claude/nest_cvmfs_fixed.csv",            "color": "#c1483a"},
    {"short": "portable", "label": "Fully-bundled",
     "csv": f"{UPLOADS}/portable_sweep.csv",                "color": "#7a4fa3"},
]

NODES        = [1, 2, 4, 8, 16, 32]   # x-axis order
SCALE_PER_N  = 16                     # weak scaling: scale = SCALE_PER_N * nodes
RANKS_PER_N  = 2
THREADS      = 64
INDEGREE     = 11250
EXTRAPOLATE_INTERIOR_GAPS = True      # fill missing interior points from reference
# -----------------------------------------------------------------------------

PHASES   = ["build_nodes", "build_edges", "presim", "sim"]
PH_LABEL = {"build_nodes": "Network: create nodes",
            "build_edges": "Network: connect (edges)",
            "presim":      "Presimulation (conn. infra + MPI comm.)",
            "sim":         "Simulation (1000 ms)"}
PH_COL   = {"build_nodes": "#7fb069", "build_edges": "#2a9d8f",
            "presim":      "#e9a13b", "sim":         "#c1483a"}
NUMCOLS  = ["vps", "procs", "threads", "neurons", "network_size",
            "connections_global", *PHASES, "mem_after_sim", "rate"]

os.makedirs(OUT, exist_ok=True)


# ---- load -------------------------------------------------------------------
def load(path):
    df = pd.read_csv(path)
    for c in NUMCOLS:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=PHASES, how="all").sort_values("nodes").reset_index(drop=True)
    df["total"] = df[PHASES].sum(axis=1)
    df["extrapolated"] = False
    return df

stacks = []
for s in STACKS:
    if not os.path.exists(s["csv"]):
        print(f"[skip] {s['short']}: CSV not found ({s['csv']})")
        continue
    s = dict(s); s["df"] = load(s["csv"]); stacks.append(s)
    print(f"[ok]   {s['short']}: {len(s['df'])} runs "
          f"(nodes {list(s['df'].nodes.astype(int))})")

if not stacks:
    raise SystemExit("No stacks loaded — check CSV paths.")

# reference = first stack that covers the smallest node count (for ideal + extrap)
ref = next((s for s in stacks if 1 in set(s["df"].nodes)), stacks[0])
print(f"\nReference stack (ideal-flat baseline / extrapolation source): {ref['short']}")


# ---- verify -----------------------------------------------------------------
def verify(s):
    df = s["df"]
    print(f"\n=== {s['short']} verification ===")
    print(f"{'nodes':>5} {'neurons':>9} {'expect':>9} {'VPs':>6} {'exp':>6} "
          f"{'rate':>6} {'valid':>6}")
    for _, r in df.iterrows():
        n = int(r["nodes"]); exp_neu = SCALE_PER_N * n * INDEGREE
        exp_vp = RANKS_PER_N * THREADS * n
        ok = (abs((r["network_size"] - 2) - exp_neu) < 1
              and int(r["vps"]) == exp_vp and r["rate"] < 10)
        print(f"{n:>5} {int(r['neurons']):>9} {exp_neu:>9} {int(r['vps']):>6} "
              f"{exp_vp:>6} {r['rate']:>6.2f} {'YES' if ok else 'NO':>6}")

for s in stacks:
    verify(s)


# ---- extrapolate interior gaps (ml-anchored geometric-mean ratio) -----------
def get(df, n, ph):
    row = df.loc[df.nodes == n]
    return row[ph].values[0] if len(row) and not pd.isna(row[ph].values[0]) else None

if EXTRAPOLATE_INTERIOR_GAPS:
    ref_nodes = set(ref["df"].nodes)
    for s in stacks:
        if s is ref:
            continue
        have = set(s["df"].nodes)
        lo, hi = min(have), max(have)
        gaps = [n for n in NODES if lo < n < hi and n not in have and n in ref_nodes]
        for n in gaps:
            # clean points present in BOTH this stack and the reference
            common = sorted(have & ref_nodes)
            new = {"nodes": n, "extrapolated": True}
            for ph in PHASES:
                ratios = [get(s["df"], c, ph) / get(ref["df"], c, ph) for c in common
                          if get(s["df"], c, ph) and get(ref["df"], c, ph)]
                gm = float(np.exp(np.mean(np.log(ratios))))
                new[ph] = get(ref["df"], n, ph) * gm
            new["vps"] = RANKS_PER_N * THREADS * n
            new["neurons"] = SCALE_PER_N * n * INDEGREE
            new["network_size"] = new["neurons"] + 2
            new["total"] = sum(new[ph] for ph in PHASES)
            s["df"] = pd.concat([s["df"], pd.DataFrame([new])],
                                ignore_index=True).sort_values("nodes").reset_index(drop=True)
            print(f"[extrap] {s['short']} n={n}: "
                  + ", ".join(f"{ph}={new[ph]:.2f}" for ph in PHASES))

# merged tidy table
merged = pd.concat([s["df"].assign(stack=s["short"]) for s in stacks],
                   ignore_index=True)
merged.to_csv(f"{OUT}/nest_sweep_merged.csv", index=False)


# ---- styling ----------------------------------------------------------------
plt.rcParams.update({
    "figure.dpi": 130, "font.size": 11, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.alpha": .25,
    "grid.linewidth": .6, "axes.axisbelow": True,
})
xpos = {n: i for i, n in enumerate(NODES)}
NS = len(stacks)


# ---- FIG 1: grouped stacked bars (phases stacked; one bar per stack) --------
fig, ax = plt.subplots(figsize=(12, 6.2))
gw = 0.82                      # total width of a node group
bw = gw / NS                   # per-stack bar width
for j, s in enumerate(stacks):
    off = (j - (NS - 1) / 2) * bw
    for _, r in s["df"].iterrows():
        n = int(r["nodes"])
        if n not in xpos:
            continue
        x = xpos[n] + off
        bottom = 0
        ex = bool(r.get("extrapolated", False))
        for ph in PHASES:
            ax.bar(x, r[ph], bw, bottom=bottom, color=PH_COL[ph],
                   edgecolor="white", linewidth=.5,
                   hatch="////" if ex else None)
            bottom += r[ph]
        ax.text(x, bottom + max(ax.get_ylim()) * 0.004 + 1, s["short"],
                ha="center", va="bottom", fontsize=6.8, color="#555", rotation=90)
        if ex:
            ax.text(x, bottom + 9, "est.", ha="center", va="bottom",
                    fontsize=6.8, style="italic", color="#b00", rotation=90)
ax.set_xticks(range(len(NODES)))
ax.set_xticklabels([f"{n}\n({RANKS_PER_N*THREADS*n} VPs)" for n in NODES])
ax.set_xlabel(f"Nodes  ({RANKS_PER_N} ranks × {THREADS} threads each)")
ax.set_ylabel("Wall-clock time  [s]")
ax.set_title("NEST 3.9 HPC benchmark — weak scaling (scale = 16 × nodes)\n"
             + "  vs  ".join(s["label"] for s in stacks), fontsize=12, loc="left")
leg = [Patch(fc=PH_COL[ph], label=PH_LABEL[ph]) for ph in PHASES]
leg.append(Patch(fc="#cccccc", hatch="////", ec="white", label="extrapolated"))
ax.legend(handles=leg, loc="upper left", fontsize=8.5, framealpha=.95)
fig.text(0.99, 0.005, "bars per group, left→right: "
         + " · ".join(s["short"] for s in stacks),
         ha="right", fontsize=8, color="#777")
fig.tight_layout()
fig.savefig(f"{OUT}/fig1_weak_scaling_stacked.png", bbox_inches="tight")
plt.close(fig)


# ---- FIG 2: per-phase weak-scaling curves (flat = ideal) --------------------
fig, axes = plt.subplots(2, 2, figsize=(13, 9))
for ax, ph in zip(axes.ravel(), PHASES):
    base = get(ref["df"], min(ref["df"].nodes), ph)
    for s in stacks:
        df = s["df"].sort_values("nodes")
        ns = [int(n) for n in df.nodes if n in xpos]
        ys = [get(df, n, ph) for n in ns]
        ax.plot(np.log2(ns), ys, "o-", color=s["color"], lw=2, ms=6, label=s["label"])
        # mark extrapolated points hollow
        for _, r in df.iterrows():
            if r.get("extrapolated", False) and int(r["nodes"]) in xpos:
                ax.plot(np.log2(int(r["nodes"])), r[ph], "D",
                        color="white", mec=s["color"], mew=2, ms=10, zorder=5)
    ax.axhline(base, ls=":", color="#888", lw=1.3)
    ax.set_xticks(np.log2(NODES)); ax.set_xticklabels(NODES)
    ax.set_xlabel("Nodes"); ax.set_ylabel("Wall-clock time  [s]")
    ax.set_title(PH_LABEL[ph], fontsize=10.5, loc="left")
    ax.legend(fontsize=8)
fig.suptitle("Weak-scaling behaviour per phase  (dotted = ideal flat; "
             "hollow diamond = extrapolated)", fontsize=13, x=0.01, ha="left")
fig.tight_layout(rect=[0, 0, 1, 0.97])
fig.savefig(f"{OUT}/fig2_weak_scaling_curves.png", bbox_inches="tight")
plt.close(fig)


# ---- FIG 3: portability cost — each stack's TOTAL time relative to ref -------
others = [s for s in stacks if s is not ref]
if others:
    fig, ax = plt.subplots(figsize=(11, 5.6))
    rnodes = [n for n in NODES
              if any(get(s["df"], n, "total") for s in others) and get(ref["df"], n, "total")]
    bw3 = 0.8 / max(len(others), 1)
    for j, s in enumerate(others):
        off = (j - (len(others) - 1) / 2) * bw3
        ys, exs = [], []
        for n in rnodes:
            c = get(s["df"], n, "total"); m = get(ref["df"], n, "total")
            ys.append(c / m if (c and m) else np.nan)
            row = s["df"].loc[s["df"].nodes == n]
            exs.append(bool(row["extrapolated"].values[0]) if len(row) else False)
        xs = np.arange(len(rnodes)) + off
        bars = ax.bar(xs, ys, bw3, color=s["color"], label=s["label"],
                      edgecolor="white", linewidth=.5)
        for b, e in zip(bars, exs):
            if e:
                b.set_hatch("////")
    ax.axhline(1.0, color="#333", lw=1.4)
    ax.text(len(rnodes) - 0.5, 1.0, f" parity (= {ref['short']})",
            va="bottom", ha="right", fontsize=8.5, color="#333")
    ax.set_xticks(range(len(rnodes))); ax.set_xticklabels(rnodes)
    ax.set_xlabel("Nodes")
    ax.set_ylabel(f"total time  /  {ref['short']}   (>1 = slower than bare-metal)")
    ax.set_title("Portability cost — total time-to-solution vs bare-metal\n"
                 "(hatched = extrapolated)", fontsize=12, loc="left")
    ax.legend(fontsize=8.5, loc="upper center", bbox_to_anchor=(0.5, -0.13),
              ncol=max(len(others), 1))
    lo = np.nanmin([b.get_height() for b in ax.patches])
    hi = np.nanmax([b.get_height() for b in ax.patches])
    ax.set_ylim(min(0.9, lo - 0.05), max(1.15, hi + 0.05))
    fig.tight_layout()
    fig.savefig(f"{OUT}/fig3_portability_cost.png", bbox_inches="tight")
    plt.close(fig)

print(f"\nWrote figures + nest_sweep_merged.csv to {OUT}")
