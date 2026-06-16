#!/usr/bin/env python3
"""Poster figures — EBRAINS-themed, large readable fonts."""
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle
from matplotlib.lines import Line2D
import matplotlib.patheffects as pe
import os

OUT="/home/claude/poster_src/figures"; os.makedirs(OUT, exist_ok=True)

# ---- EBRAINS palette ----
TEAL   = "#0E8C6E"   # primary (logo green/teal, dark enough for white text)
TEALL  = "#7FCDB8"   # light teal
GREEN  = "#00B26C"
MAG    = "#DE0054"   # EBRAINS magenta accent (streaming)
RED    = "#E4063B"
BLUE   = "#1374C3"
AMBER  = "#F2A13B"
VIOLET = "#836C91"
INK    = "#23202A"
PAPER  = "#FFFFFF"
GRID   = "#D8DEDC"

plt.rcParams.update({
    "font.size":19,"font.family":"DejaVu Sans","axes.edgecolor":INK,
    "axes.linewidth":1.4,"xtick.major.width":1.4,"ytick.major.width":1.4,
    "xtick.major.size":7,"ytick.major.size":7,"axes.titlesize":21,
    "axes.labelsize":20,"figure.dpi":150,
})

def rbox(ax,x,y,w,h,fc,ec=INK,lw=1.6,r=0.035,alpha=1,ls="-"):
    b=FancyBboxPatch((x,y),w,h,boxstyle=f"round,pad=0,rounding_size={r}",
                     fc=fc,ec=ec,lw=lw,alpha=alpha,ls=ls,mutation_aspect=1)
    ax.add_patch(b); return b
def txt(ax,x,y,s,fs=18,c=INK,w="bold",ha="center",va="center",style="normal"):
    ax.text(x,y,s,fontsize=fs,color=c,fontweight=w,ha=ha,va=va,style=style,zorder=6)

# =====================================================================
# FIG A — Host / container architecture layer cake (recreates drawing.svg)
# =====================================================================
fig,ax=plt.subplots(figsize=(9.2,10.4)); ax.set_xlim(0,10); ax.set_ylim(0,11.6); ax.axis("off")

# container boundary (covers app + middleware), dashed magenta
rbox(ax,0.35,5.55,9.3,5.55,fc="#FCE8EF",ec=MAG,lw=3.2,r=0.06,ls=(0,(6,4)))
txt(ax,5,11.32,"Portable software layer  (Apptainer image)",17,MAG)

# Application layer
rbox(ax,0.6,9.35,8.8,1.5,fc="#E8F6F0",ec=TEAL,lw=1.8)
txt(ax,5,10.62,"Application & user code",16,TEAL)
apps=["NEST","Arbor","Neuron","PyTorch","JAX"]
for i,a in enumerate(apps):
    xx=1.05+i*1.68
    rbox(ax,xx,9.55,1.45,0.78,fc=(TEAL if a=="NEST" else "#FFFFFF"),
         ec=TEAL,lw=1.8,r=0.06)
    txt(ax,xx+0.72,9.94,a,16,("#FFFFFF" if a=="NEST" else INK))

# Middleware layer
rbox(ax,0.6,5.95,8.8,3.1,fc="#EAF1FA",ec=BLUE,lw=1.8)
txt(ax,5,8.88,"Communication & accelerator middleware",15.5,BLUE)
txt(ax,5,8.5,"all provided by EESSI  —  streamed via CVMFS, or bundled (fully-bundled image)",11.5,TEAL,w="normal")
mids=[("UCX\nRDMA transport",1.05,7.35,2.0,0.95,TEAL,13),
      ("libpmix\nwire-up client",3.2,7.35,2.0,0.95,MAG,13),
      ("libibverbs",5.35,7.35,1.75,0.95,TEAL,14),
      ("CUDA runtime\n(toolkit)",7.25,7.35,2.1,0.95,GREEN,13),
      ("EESSI environment   ·   GCC · OpenMPI 5 · Python · math libs",1.05,6.15,8.3,0.9,TEAL,15)]
for s,x,y,w,h,c,fs in mids:
    rbox(ax,x,y,w,h,fc="#FFFFFF",ec=c,lw=1.7,r=0.05); txt(ax,x+w/2,y+h/2,s,fs,c)

# ---- host (outside container) ----
txt(ax,5,5.32,"System software   (host, outside container)",16,INK)
rbox(ax,0.6,3.55,8.8,1.55,fc="#F3EFF6",ec=VIOLET,lw=1.8)
hosts=[("SLURM\nsrun · slurmstepd",1.05,3.75,2.6,1.15,VIOLET),
       ("Apptainer\ncontainer runtime",3.9,3.75,2.6,1.15,VIOLET),
       ("PMIx server",6.75,3.75,2.15,1.15,MAG)]
for s,x,y,w,h,c in hosts:
    rbox(ax,x,y,w,h,fc="#FFFFFF",ec=c,lw=1.7,r=0.05); txt(ax,x+w/2,y+h/2,s,14.5,c)

# Kernel
rbox(ax,0.6,1.95,8.8,1.35,fc="#ECECEC",ec=INK,lw=1.8)
txt(ax,5,2.98,"Linux kernel  &  hardware drivers (shared)",15.5,INK)
for s,x,w in [("mlx5 / verbs",1.05,2.3),("RDMA core",3.55,2.1),("nvidia driver · libcuda · GPUDirect",5.85,3.5)]:
    rbox(ax,x,2.12,w,0.66,fc="#FFFFFF",ec=INK,lw=1.5,r=0.05)
    txt(ax,x+w/2,2.45,s,12.5 if "libcuda" in s else 13.5,INK)

# Hardware
rbox(ax,0.6,0.35,8.8,1.3,fc=INK,ec=INK,lw=1.8)
txt(ax,5,1.32,"Compute nodes",15,"#FFFFFF")
for s,x in [("InfiniBand HDR",2.4),("GPU",5.1),("AMD EPYC (zen2)",6.9)]:
    txt(ax,x,0.72,s,13.5,TEALL,w="bold")

# PMIx wire-up arrow crossing the boundary (host PMIx server -> libpmix in container)
ar=FancyArrowPatch((7.8,4.9),(4.2,7.65),arrowstyle="-|>",mutation_scale=26,
                   lw=3.0,color=MAG,connectionstyle="arc3,rad=-0.28",zorder=7)
ax.add_patch(ar)
txt(ax,6.95,5.78,"PMIx\nwire-up",13.5,MAG)
fig.tight_layout(); fig.savefig(f"{OUT}/arch_layers.pdf",bbox_inches="tight")
fig.savefig(f"{OUT}/arch_layers.png",bbox_inches="tight",dpi=150); plt.close(fig)

# =====================================================================
# FIG B — CVMFS streaming build/run + EuroHPC portability (hero figure)
# =====================================================================
fig,ax=plt.subplots(figsize=(12.6,7.2)); ax.set_xlim(0,16); ax.set_ylim(0,9); ax.axis("off")

# 1) build once
rbox(ax,0.3,3.4,3.5,3.2,fc="#E8F6F0",ec=TEAL,lw=2.4)
txt(ax,2.05,6.25,"BUILD ONCE",18,TEAL)
rbox(ax,0.7,4.4,2.7,1.45,fc="#FFFFFF",ec=TEAL,lw=2,r=0.06)
txt(ax,2.05,5.5,"QEMU multi-arch",13.5,INK); txt(ax,2.05,5.08,"NEST: AVX2 + AVX-512",12.5,MAG)
txt(ax,2.05,4.66,"(one host)",12,VIOLET)
txt(ax,2.05,3.9,"thin multi-arch image",13,TEAL)

# 2) CVMFS / EESSI streaming cloud
cloud=FancyBboxPatch((4.7,4.0),5.2,4.3,boxstyle="round,pad=0,rounding_size=0.5",
                     fc="#FCE8EF",ec=MAG,lw=3.0); ax.add_patch(cloud)
txt(ax,7.3,7.85,"CVMFS  ·  EESSI",20,MAG)
txt(ax,7.3,7.25,"base stack streamed on demand",15,INK)
for i,(s) in enumerate(["GCC / OpenMPI 5 / PMIx","Python · GSL · Boost",
                        "EESSI base, arch-optimised","auto-selected: zen2 · zen3 · skylake_avx512"]):
    txt(ax,7.3,6.65-i*0.55,"•  "+s,13.5,INK,w="normal")
# streaming arrows (animated look) into container
for yy in (4.6,5.2,5.8):
    ar=FancyArrowPatch((3.9,yy),(4.85,yy),arrowstyle="-|>",mutation_scale=20,
                       lw=2.6,color=MAG); ax.add_patch(ar)
txt(ax,4.35,6.35,"mount\n/cvmfs",12.5,MAG)

# 3) run anywhere — EuroHPC sites
rbox(ax,10.7,3.2,5.0,5.4,fc="#EAF1FA",ec=BLUE,lw=2.4)
txt(ax,13.2,8.25,"RUN ANYWHERE",18,BLUE)
txt(ax,13.2,7.7,"build once · run at any EuroHPC site",13.5,INK,w="normal")
sites=["JUSUF (JSC)","JURECA-DC","LUMI / EuroHPC","MareNostrum","any /cvmfs site"]
for i,s in enumerate(sites):
    yy=7.0-i*0.78
    rbox(ax,11.1,yy-0.3,4.2,0.62,fc="#FFFFFF",ec=BLUE,lw=1.7,r=0.06)
    txt(ax,13.2,yy,s,14.5,(TEAL if i==0 else INK))
# big stream arrow cloud->sites
ar=FancyArrowPatch((9.95,5.9),(10.65,5.9),arrowstyle="-|>",mutation_scale=26,
                   lw=3.2,color=MAG); ax.add_patch(ar)
txt(ax,10.3,6.35,"stream",12.5,MAG)
# thin sif travels too
ar2=FancyArrowPatch((3.85,4.2),(11.0,3.5),arrowstyle="-|>",mutation_scale=22,lw=2.4,
                    color=TEAL,connectionstyle="arc3,rad=0.18",ls=(0,(5,3))); ax.add_patch(ar2)
txt(ax,7.3,2.9,"same thin container ships to every site — heavy stack stays on CVMFS",14,TEAL)
fig.tight_layout(); fig.savefig(f"{OUT}/cvmfs_streaming.pdf",bbox_inches="tight")
fig.savefig(f"{OUT}/cvmfs_streaming.png",bbox_inches="tight",dpi=150); plt.close(fig)

# =====================================================================
# RESULTS — load data
# =====================================================================
df=pd.read_csv("/mnt/user-data/outputs/nest_sweep_merged.csv")
NODES=[1,2,4,8,16,32]
SL={"ml":"Bare-metal","cvmfs":"CVMFS-streamed","portable":"Fully-bundled"}
SC={"ml":BLUE,"cvmfs":MAG,"portable":VIOLET}
PH=["build_nodes","build_edges","presim","sim"]
PHL={"build_nodes":"create nodes","build_edges":"connect edges",
     "presim":"presim (comm.)","sim":"simulation"}
PHC={"build_nodes":GREEN,"build_edges":TEAL,"presim":AMBER,"sim":RED}
stacks=[s for s in ["ml","cvmfs","portable"] if s in set(df["stack"])]
xi={n:i for i,n in enumerate(NODES)}

def get(s,n,c):
    r=df[(df["stack"]==s)&(df.nodes==n)]
    return r[c].values[0] if len(r) and not pd.isna(r[c].values[0]) else None

# ---- R1: weak-scaling stacked bars (3 stacks) ----
fig,ax=plt.subplots(figsize=(11,5.9))
W=0.82/len(stacks)
for j,s in enumerate(stacks):
    off=(j-(len(stacks)-1)/2)*W
    for n in NODES:
        b=0
        for ph in PH:
            v=get(s,n,ph)
            if v is None: continue
            ax.bar(xi[n]+off,v,W,bottom=b,color=PHC[ph],edgecolor="white",lw=.8)
            b+=v
ax.set_xticks(range(len(NODES))); ax.set_xticklabels([f"{n}\n{128*n} VPs" for n in NODES])
ax.set_xlabel("compute nodes  (2 ranks × 64 threads)"); ax.set_ylabel("wall-clock time  [s]")
ax.set_title("Weak scaling — time-to-solution by phase",fontweight="bold",pad=12)
ax.grid(axis="y",color=GRID,lw=1); ax.set_axisbelow(True)
h=[Line2D([0],[0],marker="s",ls="",ms=15,mfc=PHC[p],mec="white",label=PHL[p]) for p in PH]
h+=[Line2D([0],[0],marker="s",ls="",ms=0,label="  bars: "+" · ".join(SL[s] for s in stacks))]
ax.legend(handles=h,fontsize=14,loc="upper left",frameon=True)
fig.tight_layout(); fig.savefig(f"{OUT}/res_weak_stacked.pdf",bbox_inches="tight")
fig.savefig(f"{OUT}/res_weak_stacked.png",bbox_inches="tight",dpi=150); plt.close(fig)

# ---- R2: portability cost — two panels: total time-to-solution + sustained sim ----
df["total"]=df[PH].sum(axis=1)
others=[s for s in stacks if s!="ml"]
rn=[n for n in NODES]; W2=0.8/len(others)
def ratio_panel(ax,metric,ylab,title,ymin,ymax):
    for j,s in enumerate(others):
        off=(j-(len(others)-1)/2)*W2
        ys=[(get(s,n,metric)/get("ml",n,metric)) if get(s,n,metric) and get("ml",n,metric) else np.nan for n in rn]
        ax.bar(np.arange(len(rn))+off,ys,W2,color=SC[s],edgecolor="white",lw=.8,label=SL[s])
    ax.axhline(1.0,color=INK,lw=2)
    ax.set_xticks(range(len(rn))); ax.set_xticklabels(rn)
    ax.set_xlabel("compute nodes"); ax.set_ylabel(ylab)
    ax.set_ylim(ymin,ymax); ax.set_title(title,fontweight="bold",pad=10,fontsize=18)
    ax.grid(axis="y",color=GRID,lw=1); ax.set_axisbelow(True)

fig,axes=plt.subplots(1,2,figsize=(13,5.2))
ratio_panel(axes[0],"total","total time  /  bare-metal","Time-to-solution",0.85,1.12)
axes[0].text(len(rn)-0.5,1.004,"parity",ha="right",va="bottom",fontsize=13,color=INK)
ratio_panel(axes[1],"sim","sim time  /  bare-metal","Sustained simulation",0.80,1.15)
axes[1].text(len(rn)-0.5,1.004,"parity",ha="right",va="bottom",fontsize=13,color=INK)
axes[0].legend(fontsize=14,loc="upper left")
fig.suptitle("Portability cost ≈ 0  (container vs bare-metal)",fontweight="bold",fontsize=20,y=1.02)
fig.tight_layout(); fig.savefig(f"{OUT}/res_portability.pdf",bbox_inches="tight")
fig.savefig(f"{OUT}/res_portability.png",bbox_inches="tight",dpi=150); plt.close(fig)

# single-panel total-time version (for the teaser slide)
fig,ax=plt.subplots(figsize=(10.5,5.4))
ratio_panel(ax,"total","total time  /  bare-metal","Portability cost ≈ 0  (container vs bare-metal)",0.85,1.12)
ax.text(len(rn)-0.5,1.004,"parity = bare-metal",ha="right",va="bottom",fontsize=14,color=INK)
ax.legend(fontsize=15,loc="upper right")
fig.tight_layout(); fig.savefig(f"{OUT}/res_portability_total.png",bbox_inches="tight",dpi=150); plt.close(fig)

# ---- R3: real-time factor (beNNch metric) ----
fig,ax=plt.subplots(figsize=(10.5,5.4))
for s in stacks:
    ns=[n for n in NODES if get(s,n,"sim") is not None]
    ys=[get(s,n,"sim") for n in ns]   # model time = 1 s -> rtf == sim seconds
    ax.plot(np.log2(ns),ys,"o-",color=SC[s],lw=3.2,ms=11,label=SL[s])
ax.set_xticks(np.log2(NODES)); ax.set_xticklabels(NODES)
ax.set_xlabel("compute nodes"); ax.set_ylabel("real-time factor  $T_{wall}/T_{model}$")
ax.set_title("State propagation — all stacks overlap",fontweight="bold",pad=12)
ax.grid(color=GRID,lw=1); ax.set_axisbelow(True); ax.legend(fontsize=15,loc="upper left")
fig.tight_layout(); fig.savefig(f"{OUT}/res_rtf.pdf",bbox_inches="tight")
fig.savefig(f"{OUT}/res_rtf.png",bbox_inches="tight",dpi=150); plt.close(fig)

print("figures written to", OUT)
for f in sorted(os.listdir(OUT)):
    if f.endswith(".pdf"): print("  ",f)
