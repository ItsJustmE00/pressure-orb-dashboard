import re
from pathlib import Path

root = Path("out_orb_portfolio_57k")
base = (root / "tester_ustecm_BE002_12m.ini").read_text(encoding="utf-16")


def setv(t, key, val):
    return re.sub(rf"(?m)^{re.escape(key)}=.*$", f"{key}={val}", t)


for name, port, tag, fromd, tod in (
    ("tester_ustecm_SHORT_12m.ini", 3046, "mt5_SHORT_12m", "2025.09.21", "2026.09.15"),
    ("tester_ustecm_SHORT_2026.ini", 3047, "mt5_SHORT_2026", "2026.01.01", "2026.09.15"),
):
    t = base
    t = setv(t, "Port", str(port))
    t = setv(t, "FromDate", fromd)
    t = setv(t, "ToDate", tod)
    t = setv(t, "InpRiskPct", "3.0||3.0||0.1||10.0||N")
    t = setv(t, "InpTargetR", "3.0||3.0||0.3||30.0||N")
    t = setv(t, "InpMagic", "20261115||20261115||1||202611150||N")
    t = setv(t, "InpLongOnly", "false||false||0||true||N")
    t = setv(t, "InpShortOnly", "true||false||0||true||N")
    t = setv(t, "InpUseTrendFilter", "false||false||0||true||N")
    t = setv(t, "InpUseOrCloseFilter", "false||false||0||true||N")
    t = setv(t, "InpUseMomFilter", "false||false||0||true||N")
    t = setv(t, "InpUsePrevCloseFilter", "false||false||0||true||N")
    t = setv(t, "InpUsePrevWickFilter", "false||false||0||true||N")
    short_inputs = (
        "InpShortOnly=true||false||0||true||N\n"
        "InpUseShortOrFilter=true||false||0||true||N\n"
        "InpShortOrCloseMax=0.1956||0.1956||0.0001||1.0000||N\n"
        "InpUseShortMomFilter=true||false||0||true||N\n"
        "InpShortMomMax=-0.00123||-0.00123||-0.10000||0.10000||N\n"
        "InpUseShortTrendFilter=true||false||0||true||N\n"
        "InpShortTrendMin=-0.00425||-0.00425||-0.10000||0.10000||N\n"
    )
    marker = "InpDebugTrend=false||false||0||true||N"
    if marker not in t:
        raise SystemExit("debug marker missing")
    t = t.replace(marker, short_inputs + marker)
    t = re.sub(
        r"(?m)^Report=.*$",
        f"Report=C:\\\\Users\\\\moham\\\\Downloads\\\\agency-agents-main\\\\agency-agents-main\\\\out_orb_portfolio_57k\\\\{tag}",
        t,
    )
    (root / name).write_text(t, encoding="utf-16")
    print(name)
