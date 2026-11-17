import re
from pathlib import Path

root = Path("out_orb_portfolio_57k")
base = (root / "tester_ustecm_BE002_12m.ini").read_text(encoding="utf-16")


def setv(t, key, val):
    return re.sub(rf"(?m)^{re.escape(key)}=.*$", f"{key}={val}", t)


for name, port, tag, fromd, tod in (
    ("tester_ustecm_1030_12m.ini", 3044, "mt5_1030_12m", "2025.09.21", "2026.09.15"),
    ("tester_ustecm_1030_2026.ini", 3045, "mt5_1030_2026", "2026.01.01", "2026.09.15"),
):
    t = base
    t = setv(t, "Port", str(port))
    t = setv(t, "FromDate", fromd)
    t = setv(t, "ToDate", tod)
    t = setv(t, "InpRiskPct", "0.5||0.5||0.1||10.0||N")
    t = setv(t, "InpTargetR", "4.0||4.0||0.3||30.0||N")
    t = setv(t, "InpMagic", "20261114||20261114||1||202611140||N")
    t = setv(t, "InpRangeHourNY", "10||10||0||23||N")
    t = setv(t, "InpRangeMinuteNY", "30||30||0||59||N")
    t = setv(t, "InpLongOnly", "false||false||0||true||N")
    t = setv(t, "InpUseTrendFilter", "false||false||0||true||N")
    t = setv(t, "InpUseRsiFilter", "false||false||0||true||N")
    t = setv(t, "InpUseRangeRankFilter", "false||false||0||true||N")
    t = setv(t, "InpUseOrCloseFilter", "false||false||0||true||N")
    t = setv(t, "InpUseMomFilter", "false||false||0||true||N")
    t = setv(t, "InpUsePrevCloseFilter", "false||false||0||true||N")
    t = setv(t, "InpUsePrevWickFilter", "false||false||0||true||N")
    t = setv(t, "InpDebugTrend", "false||false||0||true||N")
    t = re.sub(
        r"(?m)^Report=.*$",
        f"Report=C:\\\\Users\\\\moham\\\\Downloads\\\\agency-agents-main\\\\agency-agents-main\\\\out_orb_portfolio_57k\\\\{tag}",
        t,
    )
    (root / name).write_text(t, encoding="utf-16")
    print(name)
