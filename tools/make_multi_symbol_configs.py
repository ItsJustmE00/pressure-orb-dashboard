import re
from pathlib import Path

root = Path("out_orb_portfolio_57k")
base = (root / "tester_ustecm_BE002_12m.ini").read_text(encoding="utf-16")

for symbol, port, tag in (("US30m", 3042, "US30_BE002_12m"), ("US500m", 3043, "US500_BE002_12m")):
    t = base
    t = re.sub(r"(?m)^Symbol=.*$", f"Symbol={symbol}", t)
    t = re.sub(r"(?m)^Port=.*$", f"Port={port}", t)
    t = re.sub(
        r"(?m)^Report=.*$",
        f"Report=C:\\\\Users\\\\moham\\\\Downloads\\\\agency-agents-main\\\\agency-agents-main\\\\out_orb_portfolio_57k\\\\{tag}",
        t,
    )
    path = root / f"tester_{symbol.lower()}_BE002_12m.ini"
    path.write_text(t, encoding="utf-16")
    print(path)
