"""Analyse marche multi-timeframes (< 1 an) avec proxies d'order flow.

Donnees : nas100_m15_kaggle_utc.parquet (M15 2016-2026).
Fenetre : 12 derniers mois (2025-11-09 -> 2026-11-08).
Timeframes : M15, M30, H1, H4, D1.

Proxies d'order flow (pas de tick bid/ask historique -> proxies OHLCV) :
- delta proxy par bougie : sign(close-open) * tick_volume
- absorption : gros volume, petit corps
- desequilibre : rapport volume haussier / baissier par heure
- volume profile : POC, value area 70 %, HVN / LVN
- effort vs resultat : ATR vs volume

Sortie : out_market_analysis/ (csv + rapport console).
"""
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out_market_analysis"
OUT.mkdir(exist_ok=True)

frames = []
for fname in ("nas100_m15_kaggle_utc.parquet", "nas100_m15.parquet"):
    d = pd.read_parquet(ROOT / "data_live" / fname)
    d["time"] = pd.to_datetime(d["time"], utc=True)
    frames.append(d[["time", "open", "high", "low", "close", "tick_volume", "spread"]])
df = pd.concat(frames, ignore_index=True)
df = df.sort_values("time").drop_duplicates("time", keep="last").reset_index(drop=True)
df["ny"] = df["time"].dt.tz_convert("America/New_York")
df["ny_date"] = df["ny"].dt.date
df["ny_min"] = df["ny"].dt.hour * 60 + df["ny"].dt.minute

start = pd.Timestamp("2025-11-09", tz="UTC")
end = pd.Timestamp("2026-11-08 23:59", tz="UTC")
w = df[(df["time"] >= start) & (df["time"] <= end)].reset_index(drop=True)
print(f"Fenetre : {w['time'].min()} -> {w['time'].max()}  bars={len(w)}")
print(f"Prix : min={w['low'].min():.0f} max={w['high'].max():.0f} dernier={w['close'].iloc[-1]:.2f}")

last = float(w["close"].iloc[-1])


# ---------- resampling ----------
def resample(d, rule):
    r = d.set_index("time").resample(rule, label="left", closed="left").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"),
        close=("close", "last"), volume=("tick_volume", "sum"),
        spread=("spread", "mean"),
    ).dropna()
    return r


tfs = {"M15": w, "M30": resample(w, "30min"), "H1": resample(w, "1h"),
       "H4": resample(w, "4h"), "D1": resample(w, "1D")}

print("\n================ STRUCTURE PAR TIMEFRAME ================")
struct_rows = []
for name, d in tfs.items():
    c = d["close"]
    ema20 = c.ewm(span=20, adjust=False).mean()
    ema50 = c.ewm(span=50, adjust=False).mean()
    tr = np.maximum(d["high"] - d["low"],
                    np.maximum((d["high"] - c.shift()).abs(), (d["low"] - c.shift()).abs()))
    atr = tr.rolling(14).mean()
    up = (c > ema20).mean() * 100
    golden = (ema20 > ema50).mean() * 100
    ret_y = (c.iloc[-1] / c.iloc[0] - 1) * 100
    hi, lo = d["high"].max(), d["low"].min()
    pos_in_range = (last - lo) / (hi - lo) * 100
    half = len(d) // 2
    r1 = (c.iloc[half] / c.iloc[0] - 1) * 100
    r2 = (c.iloc[-1] / c.iloc[half] - 1) * 100
    struct_rows.append({
        "tf": name, "bars": len(d), "ret_1y_pct": round(ret_y, 1),
        "ret_S1_pct": round(r1, 1), "ret_S2_pct": round(r2, 1),
        "au_dessus_ema20_pct": round(up, 1), "ema20_gt_ema50_pct": round(golden, 1),
        "atr_pct": round(atr.iloc[-1] / last * 100, 3),
        "high": round(hi, 2), "low": round(lo, 2), "pos_dans_range_pct": round(pos_in_range, 1),
    })
    d.to_csv(OUT / f"tf_{name}.csv")
st = pd.DataFrame(struct_rows)
st.to_csv(OUT / "structure_timeframes.csv", index=False)
print(st.to_string(index=False))

print("\n================ ORDER FLOW (M15, proxies OHLCV) ================")
w["delta_proxy"] = np.sign(w["close"] - w["open"]) * w["tick_volume"]
w["body"] = (w["close"] - w["open"]).abs()
w["range_bar"] = w["high"] - w["low"]
w["up_vol"] = np.where(w["close"] > w["open"], w["tick_volume"], 0)
w["dn_vol"] = np.where(w["close"] < w["open"], w["tick_volume"], 0)
w["hour_ny"] = w["ny"].dt.hour

buy_sell = w["up_vol"].sum() / max(w["dn_vol"].sum(), 1)
cum_delta = w["delta_proxy"].cumsum()
# correlation delta cumule vs prix (does flow lead price?)
corr_dp = np.corrcoef(cum_delta.iloc[::20], w["close"].iloc[::20])[0, 1]
# absorption : volume dans le top 20 % mais corps dans le bas 30 %
vq = w["tick_volume"].quantile(0.80)
bq = w["body"].quantile(0.30)
absorb_mask = (w["tick_volume"] >= vq) & (w["body"] <= bq)
absorb = w[absorb_mask]
next_close = w["close"].shift(-1)[absorb_mask]
absorb_reversal = ((absorb["close"] > absorb["open"]) &
                   (next_close < absorb["close"])).mean()
print(f"ratio buy/sell volume : {buy_sell:.3f}  (>1 = flow acheteur)")
print(f"correlation delta cumule vs prix : {corr_dp:.3f}")
print(f"bougies absorption (vol>=p80, corps<=p30) : {len(absorb)} ({len(absorb)/len(w)*100:.1f}%)")
print(f"taux de reversal apres absorption haussiere : {absorb_reversal*100:.1f}%")
w[["time", "open", "high", "low", "close", "tick_volume", "delta_proxy"]].to_csv(
    OUT / "m15_flow.csv", index=False)

print("\n--- delta par heure NY (M15, session US) ---")
sess = w[(w["ny_min"] >= 570) & (w["ny_min"] < 960)]
hourly = sess.groupby("hour_ny").agg(
    vol=("tick_volume", "sum"), up_vol=("up_vol", "sum"), dn_vol=("dn_vol", "sum"),
    delta=("delta_proxy", "sum"), bars=("delta_proxy", "count"),
    avg_range=("range_bar", "mean"),
)
hourly["ratio_bs"] = hourly["up_vol"] / hourly["dn_vol"].replace(0, np.nan)
hourly = hourly.round(2)
print(hourly.to_string())
hourly.to_csv(OUT / "hourly_flow.csv")

print("\n--- distribution volume par tranche horaire (part du volume journalier) ---")
day_vol = sess.groupby("ny_date")["tick_volume"].transform("sum")
sess = sess.assign(vol_share=sess["tick_volume"] / day_vol)
share = sess.groupby("hour_ny")["vol_share"].mean() * 100
print(share.round(1).to_string())
share.to_csv(OUT / "hourly_vol_share.csv")

print("\n================ VOLUME PROFILE (1 an, M15) ================")
bins = np.arange(w["low"].min() // 10 * 10, w["high"].max() // 10 * 10 + 11, 10)
prof, _ = np.histogram(w["close"], bins=bins, weights=w["tick_volume"])
prof_df = pd.DataFrame({"bin": bins[:-1] + 5, "volume": prof})
prof_df = prof_df.sort_values("volume", ascending=False).reset_index(drop=True)
total = prof_df["volume"].sum()
poc = prof_df.iloc[0]["bin"]
va = [poc]
acc = prof_df.iloc[0]["volume"]
i = 1
while acc < total * 0.70 and i < len(prof_df):
    va.append(prof_df.iloc[i]["bin"])
    acc += prof_df.iloc[i]["volume"]
    i += 1
va_lo, va_hi = min(va), max(va)
print(f"POC (plus gros volume) : {poc:.0f}")
print(f"Value area 70 % : {va_lo:.0f} - {va_hi:.0f}")
print(f"Prix actuel {last:.2f} -> {'DANS la value area' if va_lo <= last <= va_hi else 'HORS value area'}")
print("Top 8 niveaux de volume (HVN) :")
print(prof_df.head(8)[["bin", "volume"]].to_string(index=False))
# LVN : bins sous p20 entre va_lo et va_hi
in_va = prof_df[(prof_df["bin"] >= va_lo) & (prof_df["bin"] <= va_hi)]
lvn = in_va[in_va["volume"] <= in_va["volume"].quantile(0.20)].sort_values("bin")
print(f"LVN (zones creuses dans la value area) : {[f'{b:.0f}' for b in lvn['bin'].tolist()[:10]]}")
prof_df.to_csv(OUT / "volume_profile.csv", index=False)

print("\n================ COMPORTEMENT OUVERTURE 09:30 (M15) ================")
days = []
for date, g in w.groupby("ny_date"):
    g = g[(g["ny_min"] >= 570) & (g["ny_min"] < 960)].sort_values("ny_min")
    if len(g) < 5:
        continue
    op = g.iloc[0]
    if int(op["ny_min"]) != 570:
        continue
    orh, orl = op["high"], op["low"]
    rest = g.iloc[1:]
    day_vol_total = g["tick_volume"].sum()
    or_vol = op["tick_volume"]
    break_up = float(rest["high"].max() > orh) if len(rest) else np.nan
    break_dn = float(rest["low"].min() < orl) if len(rest) else np.nan
    first15 = rest.head(3)
    followed_up = float((first15["close"].max() > orh)) if break_up else np.nan
    days.append({
        "date": date, "or_high": orh, "or_low": orl,
        "or_range": orh - orl, "or_vol": or_vol, "day_vol": day_vol_total,
        "or_vol_share": or_vol / day_vol_total,
        "break_up": break_up, "break_dn": break_dn,
    })
d_days = pd.DataFrame(days)
print(f"jours analyses : {len(d_days)}")
print(f"cassure du high OR : {d_days['break_up'].mean()*100:.1f}%")
print(f"cassure du low OR : {d_days['break_dn'].mean()*100:.1f}%")
print(f"range OR moyen : {d_days['or_range'].mean():.1f} pts (mediane {d_days['or_range'].median():.1f})")
print(f"part du volume dans le range 09:30-09:45 : {d_days['or_vol_share'].mean()*100:.1f}%")
# OR rank : corrélation taille OR vs amplitude jour
d_days = d_days.set_index("date")
day_range = w.groupby("ny_date").agg(day_range=("range_bar", "max"))
d_days["day_range"] = day_range["day_range"]
corr_or = d_days[["or_range", "day_range"]].corr().iloc[0, 1]
print(f"correlation taille OR vs amplitude du jour : {corr_or:.3f}")
d_days.reset_index().to_csv(OUT / "opening_range_stats.csv", index=False)

print("\n================ TREND DAILY (D1) ================")
d1 = tfs["D1"].copy()
d1["ret"] = d1["close"].pct_change()
up_days = (d1["ret"] > 0).mean() * 100
big_up = (d1["ret"] > 0.01).sum()
big_dn = (d1["ret"] < -0.01).sum()
worst = d1["ret"].min() * 100
best = d1["ret"].max() * 100
max_dd = ((d1["close"] / d1["close"].cummax()) - 1).min() * 100
print(f"jours haussiers : {up_days:.1f}%  |  jours >+1% : {big_up}  jours <-1% : {big_dn}")
print(f"pire jour : {worst:.1f}%  meilleur jour : +{best:.1f}%  max drawdown buy&hold : {max_dd:.1f}%")

print("\n================ SYNTHÈSE BOT ORB (fenetre < 1 an) ================")
print(f"- Regime : {'haussier' if struct_rows[-1]['ret_S2_pct'] > 0 else 'baissier'} "
      f"sur S2 ({struct_rows[-1]['ret_S2_pct']}% en D1), prix a "
      f"{struct_rows[-1]['pos_dans_range_pct']:.0f}% du range annuel")
print(f"- Flow : ratio buy/sell {buy_sell:.2f}, correlation delta-prix {corr_dp:.2f}")
print(f"- Heure la plus active : {hourly['vol'].idxmax()}h NY "
      f"({share.max():.0f}% du volume journalier en moyenne a {share.idxmax()}h)")
print(f"- Cassure OR high {d_days['break_up'].mean()*100:.0f}% vs low {d_days['break_dn'].mean()*100:.0f}%")
