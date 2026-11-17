import re
from pathlib import Path

root = Path("out_orb_portfolio_57k")
base = (root / "tester_ustecm_SHORT_12m.ini").read_text(encoding="utf-16")


def setv(t, key, val):
    return re.sub(rf"(?m)^{re.escape(key)}=.*$", f"{key}={val}", t)


for name, port, tag, fromd, tod in (
    ("tester_ustecm_BOTH_12m.ini", 3048, "mt5_BOTH_12m", "2025.09.21", "2026.09.15"),
    ("tester_ustecm_BOTH_2026.ini", 3049, "mt5_BOTH_2026", "2026.01.01", "2026.09.15"),
):
    t = base
    t = setv(t, "Port", str(port))
    t = setv(t, "FromDate", fromd)
    t = setv(t, "ToDate", tod)
    t = setv(t, "InpShortOnly", "false||false||0||true||N")
    t = setv(t, "InpUseTrendFilter", "true||false||0||true||N")
    t = setv(t, "InpUseOrCloseFilter", "true||false||0||true||N")
    t = setv(t, "InpUseMomFilter", "true||false||0||true||N")
    t = re.sub(
        r"(?m)^Report=.*$",
        f"Report=C:\\\\Users\\\\moham\\\\Downloads\\\\agency-agents-main\\\\agency-agents-main\\\\out_orb_portfolio_57k\\\\{tag}",
        t,
    )
    (root / name).write_text(t, encoding="utf-16")
    print(name)
