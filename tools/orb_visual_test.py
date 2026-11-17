"""Test visuel de la strategie ORB BOTH : graphiques PNG.

Genere dans out_orb_manage/ :
1. courbes d'equite OOS+recent : baseline 2R vs 1R vs 3R vs variantes gestion
2. trades sur le prix (3 derniers mois de donnees)
3. distribution des R multiples
4. performance par heure d'entree
5. rendement par mois
Ouvre ensuite l'explorateur sur le dossier.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out_orb_manage"
plt.rcParams.update({"figure.facecolor": "#0b1120", "axes.facecolor": "#0b1120",
                     "axes.edgecolor": "#334155", "axes.labelcolor": "#e2e8f0",
                     "text.color": "#e2e8f0", "xtick.color": "#94a3b8",
                     "ytick.color": "#94a3b8", "grid.color": "#1e293b"})

ACC = 57000.0
RISK = 0.005

baseline = pd.read_csv(OUT / "trades_baseline.csv", parse_dates=["date"])
one_r = pd.read_csv("out_orb_target_sweep/aggr_t1.0_m2.csv", parse_dates=["date"])
three_r = pd.read_csv("out_orb_both_oos/trades_r0.005_c1.7_e1.csv", parse_dates=["date"])


def equity(tr, start, end):
    d = tr[(tr["date"] >= start) & (tr["date"] <= end)].sort_values("date")
    bal = ACC
    xs, ys = [], []
    for _, row in d.iterrows():
        bal *= 1.0 + RISK * row["r_multiple"]
        xs.append(row["date"])
        ys.append(bal)
    return xs, ys


def eq_curve(tr, start, end):
    """Courbe barre par barre (intercalee) pour un rendu visuel lisse."""
    d = tr[(tr["date"] >= start) & (tr["date"] <= end)].sort_values("date")
    bal = ACC
    xs, ys = [], []
    if d.empty:
        return xs, ys
    # point de depart
    xs.append(d["date"].iloc[0]); ys.append(bal)
    for _, row in d.iterrows():
        bal *= 1.0 + RISK * row["r_multiple"]
        xs.append(row["date"]); ys.append(bal)
    return xs, ys


# ---------- 1. equite OOS + recent ----------
oos_start, oos_end = pd.Timestamp("2022-01-01"), pd.Timestamp("2026-09-15")
fig, ax = plt.subplots(figsize=(12, 6))
series = [
    ("ORB 2R max2 (baseline actuel)", baseline, "#38bdf8"),
    ("ORB 1R max2 (demande initiale)", one_r, "#fbbf24"),
    ("ORB 3R max1 (ancien)", three_r, "#a78bfa"),
]
for label, tr, color in series:
    xs, ys = eq_curve(tr, oos_start, oos_end)
    ax.plot(xs, ys, label=label, color=color, linewidth=1.6)
ax.axhline(ACC, color="#475569", linestyle="--", linewidth=0.8)
ax.set_title("ORB BOTH USTECm — équité 57 000 $ (0,5 % risque/trade)\nOOS 2022-2025 + récent 2025-2026 — données réelles M15")
ax.set_ylabel("Solde ($)")
ax.legend(loc="upper left", framealpha=0.2)
ax.grid(True, alpha=0.4)
fig.tight_layout()
fig.savefig(OUT / "1_equity_curves.png", dpi=110)
plt.close(fig)

# ---------- 2. trades sur le prix (3 derniers mois) ----------
import importlib.util, io, sys
spec = importlib.util.spec_from_file_location("oos", ROOT / "tools" / "orb_both_oos.py")
mod = importlib.util.module_from_spec(spec)
_old = sys.stdout; sys.stdout = io.StringIO()
spec.loader.exec_module(mod)
sys.stdout = sys._stdout if hasattr(sys, "_stdout") else sys.__stdout__
bars = mod.load_bars(["data_live/nas100_m15_kaggle_utc.parquet", "data_live/nas100_m15.parquet"])
recent_bars = bars[bars["time"] >= pd.Timestamp("2026-06-15", tz="UTC")]

tr = baseline[(baseline["date"] >= pd.Timestamp("2026-06-15"))].copy()
fig, ax = plt.subplots(figsize=(14, 6))
ax.plot(recent_bars["time"], recent_bars["close"], color="#94a3b8", linewidth=0.5, alpha=0.8)
wins = tr[tr["r_multiple"] > 0]
loss = tr[tr["r_multiple"] <= 0]
ax.scatter(wins["date"], wins["entry"], color="#22c55e", s=42, marker="^",
           label=f"gagnants ({len(wins)})", zorder=5, edgecolors="white", linewidths=0.5)
ax.scatter(loss["date"], loss["entry"], color="#ef4444", s=42, marker="v",
           label=f"perdants ({len(loss)})", zorder=5, edgecolors="white", linewidths=0.5)
ax.set_title("Trades ORB 2R max2 sur le prix USTECm — 3 derniers mois (juin-sept 2026)")
ax.set_ylabel("Prix")
ax.legend(loc="upper left", framealpha=0.2)
ax.grid(True, alpha=0.4)
fig.tight_layout()
fig.savefig(OUT / "2_trades_on_price.png", dpi=110)
plt.close(fig)

# ---------- 3. distribution des R ----------
fig, ax = plt.subplots(figsize=(10, 5))
d = baseline[(baseline["date"] >= oos_start)]
ax.hist(d["r_multiple"], bins=40, color="#38bdf8", edgecolor="#0b1120")
ax.axvline(0, color="#ef4444", linewidth=1)
ax.axvline(d["r_multiple"].mean(), color="#fbbf24", linewidth=1.2,
           label=f"moyenne {d['r_multiple'].mean():.3f}R")
ax.set_title("Distribution des R multiples — baseline 2R (OOS 2022-2026)")
ax.set_xlabel("R multiple (net de coût)")
ax.legend(framealpha=0.2)
ax.grid(True, alpha=0.4)
fig.tight_layout()
fig.savefig(OUT / "3_r_distribution.png", dpi=110)
plt.close(fig)

# ---------- 4. par heure d'entree ----------
d = baseline.copy()
d["hour"] = pd.to_datetime(d["entry_time"], utc=True).dt.hour
by_h = d.groupby("hour").agg(trades=("r_multiple", "count"), avg_r=("r_multiple", "mean"))
fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.5))
a1.bar(by_h.index, by_h["trades"], color="#38bdf8")
a1.set_title("Nombre de trades par heure d'entrée (NY)")
a1.grid(True, alpha=0.4, axis="y")
colors = ["#22c55e" if v > 0 else "#ef4444" for v in by_h["avg_r"]]
a2.bar(by_h.index, by_h["avg_r"], color=colors)
a2.axhline(0, color="#475569", linewidth=0.8)
a2.set_title("avg R par heure d'entrée (NY)")
a2.grid(True, alpha=0.4, axis="y")
fig.tight_layout()
fig.savefig(OUT / "4_by_hour.png", dpi=110)
plt.close(fig)

# ---------- 5. rendement mensuel ----------
d = baseline[(baseline["date"] >= oos_start)].copy()
d["month"] = d["date"].dt.to_period("M")
monthly = d.groupby("month")["r_multiple"].apply(lambda r: (1 + RISK * r).prod() - 1) * 100
fig, ax = plt.subplots(figsize=(12, 4.5))
colors = ["#22c55e" if v > 0 else "#ef4444" for v in monthly.values]
ax.bar([str(m) for m in monthly.index], monthly.values, color=colors)
ax.set_title("Rendement mensuel % — baseline 2R")
ax.tick_params(axis="x", rotation=90, labelsize=7)
ax.grid(True, alpha=0.4, axis="y")
fig.tight_layout()
fig.savefig(OUT / "5_monthly_returns.png", dpi=110)
plt.close(fig)

print("graphiques generes :")
for p in sorted(OUT.glob("*.png")):
    print(" -", p)
