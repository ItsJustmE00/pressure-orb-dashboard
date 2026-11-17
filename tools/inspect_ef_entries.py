import re
from pathlib import Path

import pandas as pd

LOG = Path(
    r"C:\Users\moham\AppData\Roaming\MetaQuotes\Terminal"
    r"\D0E8209F77C8CF37AD8BF550E51FF075\Tester\logs\20261113.log"
)
t = LOG.read_text(encoding="utf-16", errors="replace")
parts = []
last = 0
for m in re.finditer(r"final balance ([\d.]+) USD", t):
    seg = t[last:m.end()]
    last = m.end()
    ents = re.findall(r"(\d{4}\.\d{2}\.\d{2}) \d{2}:\d{2}:\d{2}.*?ORB entry (BUY|SELL)", seg)
    parts.append((float(m.group(1)), ents))
bal, ents = parts[-1]
dates = pd.to_datetime([d.replace(".", "-") for d, _ in ents])
d = pd.read_csv("out_orb_entry_features/nas100_entry_features.csv")
d["date"] = pd.to_datetime(d["date"])
x = d[d["date"].isin(dates)][[
    "date", "prev_mom6", "prev_upper_wick", "or_close_pos",
    "prev_close_pos", "trend_daily", "r_multiple",
]]
print("entries", len(ents), "matched", len(x))
print(x.head(25).to_string(index=False))
print("prev_upper_wick > 0.07838:", (x["prev_upper_wick"] > 0.07838).sum(), "/", len(x))
print("prev_mom6 <= 0.00123:", (x["prev_mom6"] <= 0.00123).sum(), "/", len(x))
