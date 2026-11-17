import pandas as pd

cols = ["combo", "is_n", "is_R", "is_t", "oos_n", "oos_R", "oos_t", "rec_n", "rec_R", "rec_t"]
for s in ["nas100", "us30"]:
    print("\n" + s)
    df = pd.read_csv(f"out_orb_combo_eval/{s}_combos.csv")
    print(df.sort_values("is_R", ascending=False).head(12)[cols].round(3).to_string(index=False))
