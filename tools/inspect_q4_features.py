import pandas as pd

d = pd.read_csv("out_orb_entry_features/nas100_entry_features.csv")
d["date"] = pd.to_datetime(d["date"])
dates = pd.to_datetime([
    "2025-11-19", "2025-12-02", "2025-12-19",
    "2025-12-23", "2025-12-26",
])
x = d[d["date"].isin(dates)]
print(x[[
    "date", "or_close_pos", "prev_mom6", "prev_upper_wick",
    "prev_close_pos", "prev_body_ratio", "r_multiple",
]].to_string(index=False))
