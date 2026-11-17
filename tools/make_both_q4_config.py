import re
from pathlib import Path

root = Path("out_orb_portfolio_57k")
t = (root / "tester_ustecm_BOTH_12m.ini").read_text(encoding="utf-16")
t = re.sub(r"(?m)^Port=.*$", "Port=3050", t)
t = re.sub(r"(?m)^FromDate=.*$", "FromDate=2025.09.21", t)
t = re.sub(r"(?m)^ToDate=.*$", "ToDate=2025.12.31", t)
t = re.sub(
    r"(?m)^Report=.*$",
    r"Report=C:\\Users\\moham\\Downloads\\agency-agents-main\\agency-agents-main\\out_orb_portfolio_57k\\mt5_BOTH_q4",
    t,
)
(root / "tester_ustecm_BOTH_q4.ini").write_text(t, encoding="utf-16")
print("ok")
