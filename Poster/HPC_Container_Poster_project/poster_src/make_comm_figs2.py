#!/usr/bin/env python3
"""Communication microbenchmark figures for the poster (real data)."""
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import os

UP="/mnt/user-data/uploads"; OUT="/home/claude/poster_src/figures"; os.makedirs(OUT,exist_ok=True)
TEAL="#0E8C6E"; MAG="#DE0054"; INK="#23202A"; GRID="#D8DEDC"
CEN={"Karolina":TEAL,"JURECA":MAG}
ENV_LS={"native":"-","container":"--"}; ENV_MK={"native":"o","container":"s"}
ENV_FILL={"native":"full","container":"none"}; ENV_LAB={"native":"Native","container":"Apptainer"}

plt.rcParams.update({"font.size":18,"font.family":"DejaVu Sans","axes.edgecolor":INK,
  "axes.linewidth":1.5,"xtick.major.width":1.5,"ytick.major.width":1.5,
  "xtick.major.size":7,"ytick.major.size":7,"xtick.direction":"in","ytick.direction":"in",
  "xtick.top":True,"ytick.right":True,"axes.titlesize":21,"axes.labelsize":19,"figure.dpi":150})

def legend(ax):
    h=[plt.Line2D([0],[0],color=CEN[c],lw=3,label=c) for c in CEN]
    h+=[plt.Line2D([0],[0],color=INK,ls=ENV_LS[e],marker=ENV_MK[e],fillstyle=ENV_FILL[e],
                   mfc=("none" if e=="container" else INK),ms=10,lw=2.2,label=ENV_LAB[e]) for e in ENV_LS]
    ax.legend(handles=h,fontsize=14,loc="best",framealpha=.95)

def bytefmt(x,_):
    for u in ["B","K","M","G"]:
        if x<1024: return f"{x:.0f}{u}"
        x/=1024
    return f"{x:.0f}T"

# ============ 1) OSU MPI Init (embedded data) ============
INIT={
 "Karolina":{"native":{"nodes":[1,2,4,8,16,32,64,128,256],
    "avg":[3611,3695,3571.5,3748,3838.5,3902.5,4090,4367,5575],
    "lo":[37,320,193.5,91,144.5,129.5,132,359,764],"hi":[28,309,265.5,145,290.5,265.5,618,1569,4847]},
   "container":{"nodes":[1,2,4,8,16,32,64,128,256],
    "avg":[4554.5,3867,4069.5,4281,4313.5,4439.5,4630.5,5357.5,5826.5],
    "lo":[668.5,539,115.5,457,239.5,418.5,551.5,1027.5,1351.5],"hi":[166.5,302,288.5,774,659.5,543.5,1424.5,2606.5,7594.5]}},
 "JURECA":{"native":{"nodes":[1,2,4,8,16,32,64,128],
    "avg":[2357,2477,2904,2641,2958,2955,3061,3808],
    "lo":[84,130,203,123,229,291,248,612],"hi":[137,197,308,276,314,307,265,331]},
   "container":{"nodes":[1,4,8,16,32,64,128],
    "avg":[1072,1599,1428,1422,1948,1754,1965],
    "lo":[1,775,412,259,1193,590,1038],"hi":[2,545,423,1064,2332,1213,1056]}}}
fig,ax=plt.subplots(figsize=(8.0,4.8))
for c in CEN:
    for e in ENV_LS:
        d=INIT[c][e]
        ax.errorbar(d["nodes"],d["avg"],yerr=[d["lo"],d["hi"]],color=CEN[c],
                    ls=ENV_LS[e],marker=ENV_MK[e],fillstyle=ENV_FILL[e],
                    lw=2.2,ms=8,capsize=3,elinewidth=1,alpha=.92)
ax.set_xscale("log",base=2)
ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x,_:str(int(x))))
ax.set_xlabel("number of nodes"); ax.set_ylabel("MPI_Init time  [ms]")
ax.set_title("MPI initialisation",fontweight="bold",pad=8)
ax.grid(which="major",ls=":",lw=.7,color="#aaa",alpha=.7); legend(ax)
fig.tight_layout(); fig.savefig(f"{OUT}/comm_osu_init.pdf",bbox_inches="tight")
fig.savefig(f"{OUT}/comm_osu_init.png",bbox_inches="tight",dpi=150); plt.close(fig)

# ============ 2) OSU point-to-point latency (inter-node: 2 nodes x 1 task) ============
fig,ax=plt.subplots(figsize=(8.0,4.8))
for c,f in [("Karolina","osu_latency_karolina.csv"),("JURECA","osu_latency_jureca.csv")]:
    df=pd.read_csv(f"{UP}/{f}")
    df=df[df["Nodes"]==2]                      # inter-node
    for e,env in [("Native","native"),("Container","container")]:
        d=df[df["RunEnv"]==e].sort_values("Size")
        if not len(d): continue
        ax.plot(d["Size"],d["Latency_us"],color=CEN[c],ls=ENV_LS[env],
                marker=ENV_MK[env],fillstyle=ENV_FILL[env],lw=2.2,ms=7,alpha=.92,
                markevery=2)
ax.set_xscale("log",base=2); ax.set_yscale("log")
ax.xaxis.set_major_formatter(ticker.FuncFormatter(bytefmt))
ax.set_xlabel("message size"); ax.set_ylabel("latency  [µs]")
ax.set_title("Point-to-point latency  (inter-node)",fontweight="bold",pad=8)
ax.grid(which="major",ls=":",lw=.7,color="#aaa",alpha=.7); legend(ax)
fig.tight_layout(); fig.savefig(f"{OUT}/comm_osu_latency.pdf",bbox_inches="tight")
fig.savefig(f"{OUT}/comm_osu_latency.png",bbox_inches="tight",dpi=150); plt.close(fig)

# ============ 3) NCCL all-reduce bus bandwidth (2 nodes) ============
fig,ax=plt.subplots(figsize=(8.0,4.8))
NF={("Karolina","native"):"nccl_2node_karolina_native.csv",
    ("Karolina","container"):"nccl_2node_karolina_apptainer.csv",
    ("JURECA","native"):"nccl_2node_jureca_native.csv",
    ("JURECA","container"):"nccl_2node_jureca_apptainer.csv"}
for (c,e),f in NF.items():
    d=pd.read_csv(f"{UP}/{f}")
    d=d[d["busbw_GBs"]>0]
    ax.plot(d["message_size_B"],d["busbw_GBs"],color=CEN[c],ls=ENV_LS[e],
            marker=ENV_MK[e],fillstyle=ENV_FILL[e],lw=2.2,ms=7,alpha=.92,markevery=2)
ax.set_xscale("log",base=2)
ax.xaxis.set_major_formatter(ticker.FuncFormatter(bytefmt))
ax.set_xlabel("message size"); ax.set_ylabel("bus bandwidth  [GB/s]")
ax.set_title("NCCL all-reduce bandwidth",fontweight="bold",pad=8)
ax.grid(which="major",ls=":",lw=.7,color="#aaa",alpha=.7); legend(ax)
fig.tight_layout(); fig.savefig(f"{OUT}/comm_nccl.pdf",bbox_inches="tight")
fig.savefig(f"{OUT}/comm_nccl.png",bbox_inches="tight",dpi=150); plt.close(fig)
print("comm figures written")
