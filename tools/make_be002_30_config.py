import re
from pathlib import Path

root = Path("out_orb_portfolio_57k")
t = (root / "tester_ustecm_BE002_12m.ini").read_text(encoding="utf-16")
t = re.sub(r"(?m)^Port=.*$", "Port=3041", t)
t = re.sub(r"(?m)^FromDate=.*$", "FromDate=2026.01.01", t)
t = re.sub(r"(?m)^ToDate=.*$", "ToDate=2026.09.15", t)
t = re.sub(
    r"(?m)^Report=.*$",
    r"Report=C:\\Users\\moham\\Downloads\\agency-agents-main\\agency-agents-main\\out_orb_portfolio_57k\\mt5_BE002_30",
    t,
)
(root / "tester_ustecm_BE002_30.ini").write_text(t, encoding="utf-16")
print("ok")
