import re
from pathlib import Path

ROOT = Path("out_orb_portfolio_57k")
base = (ROOT / "tester_ustecm_trend_25.ini").read_text(encoding="utf-16")

configs = [
    ("tester_ustecm_B_25.ini", 3017, "B", True, 0.8044, False, 0.00123, False, 0.9085),
    ("tester_ustecm_BE_25.ini", 3018, "BE", True, 0.8044, True, 0.00123, False, 0.9085),
    ("tester_ustecm_BEG_25.ini", 3019, "BEG", True, 0.8044, True, 0.00123, True, 0.9085),
    ("tester_ustecm_BE_30.ini", 3020, "BE30", True, 0.8044, True, 0.00123, False, 0.9085),
]

for name, port, tag, orc, orc_min, mom, mom_min, pc, pc_min in configs:
    t = base
    t = re.sub(r"Port=\d+", f"Port={port}", t)
    t = re.sub(r"(?m)^Report=.*$", lambda _m: f"Report=C:\\Users\\moham\\Downloads\\agency-agents-main\\agency-agents-main\\{ROOT}\\mt5_ustecm_{tag}", t)
    if name.endswith("_30.ini"):
        t = t.replace("InpRiskPct=2.5||2.5", "InpRiskPct=3.0||3.0")
    repl = (
        "InpRangeRankMax=0.2||0.20||0.01||1.00||N\n"
        f"InpUseOrCloseFilter={str(orc).lower()}||false||0||true||N\n"
        f"InpOrCloseMin={orc_min}||0.8044||0.0001||1.0000||N\n"
        f"InpUseMomFilter={str(mom).lower()}||false||0||true||N\n"
        f"InpMomMin={mom_min}||0.00123||-0.10000||0.10000||N\n"
        f"InpUsePrevCloseFilter={str(pc).lower()}||false||0||true||N\n"
        f"InpPrevCloseMin={pc_min}||0.9085||0.0001||1.0000||N\n"
        "InpUsePrevWickFilter=false||false||0||true||N\n"
        "InpPrevWickMax=0.07838||0.07838||0.0001||1.0000||N\n"
        "InpDebugTrend=false||false||0||true||N"
    )
    t = t.replace("InpRangeRankMax=0.2||0.20||0.01||1.00||N", repl)
    (ROOT / name).write_text(t, encoding="utf-16")
    print(name, port, tag)
