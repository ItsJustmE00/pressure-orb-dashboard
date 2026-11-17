import argparse
import subprocess
import time
from pathlib import Path

TERMINAL = Path(r"C:\Program Files\MetaTrader 5\terminal64.exe")
DATA = Path(
    r"C:\Users\moham\AppData\Roaming\MetaQuotes\Terminal"
    r"\D0E8209F77C8CF37AD8BF550E51FF075"
)
PRESETS = DATA / "MQL5" / "Presets"
PRESETS.mkdir(parents=True, exist_ok=True)

ap = argparse.ArgumentParser()
ap.add_argument("--risk", default="0.5", help="risk percent per trade (default 0.5)")
ap.add_argument("--target", default="1.0", help="target R multiple (default 1.0)")
ap.add_argument("--max-trades", type=int, default=2, help="max trades per day (default 2)")
ap.add_argument("--no-fresh-cross", action="store_true",
                help="disable fresh-cross requirement for re-entries")
args = ap.parse_args()

max_trades = max(1, int(args.max_trades))

params = {
    "InpRiskPct": args.risk,
    "InpTargetR": args.target,
    "InpMagic": "20261115",
    "InpRangeHourNY": "9",
    "InpRangeMinuteNY": "30",
    "InpCloseHourNY": "16",
    "InpCloseMinuteNY": "0",
    "InpCloseBufferMinutes": "5",
    "InpFridayCloseBufferMinutes": "10",
    "InpServerGMTOffsetHours": "0",
    "InpSlippagePoints": "30",
    "InpMaxSpreadPoints": "500",
    "InpOneTradePerDay": "true" if max_trades <= 1 else "false",
    "InpMaxTradesPerDay": str(max_trades),
    "InpRequireFreshCross": "false" if args.no_fresh_cross else "true",
    "InpLongOnly": "false",
    "InpUseTrendFilter": "true",
    "InpTrendMax": "0.002378",
    "InpUseRsiFilter": "false",
    "InpRsiMin": "56.5194859038146",
    "InpUseRangeRankFilter": "false",
    "InpRangeRankMax": "0.2",
    "InpUseOrCloseFilter": "true",
    "InpOrCloseMin": "0.8044",
    "InpUseMomFilter": "true",
    "InpMomMin": "0.00123",
    "InpUsePrevCloseFilter": "false",
    "InpPrevCloseMin": "0.9085",
    "InpUsePrevWickFilter": "false",
    "InpPrevWickMax": "0.07838",
    "InpShortOnly": "false",
    "InpUseShortOrFilter": "true",
    "InpShortOrCloseMax": "0.1956",
    "InpUseShortMomFilter": "true",
    "InpShortMomMax": "-0.00123",
    "InpUseShortTrendFilter": "true",
    "InpShortTrendMin": "-0.00425",
    "InpDebugTrend": "false",
    "InpShowDashboard": "true",
    "InpDashX": "12",
    "InpDashY": "24",
    "InpDashFontSize": "9",
}

set_path = PRESETS / "BOTH.set"
set_path.write_text(
    "\n".join(f"{k}={v}" for k, v in params.items()) + "\n",
    encoding="utf-16",
)

startup = (
    "[Common]\n"
    "EnableExperts=1\n"
    "\n"
    "[StartUp]\n"
    "Symbol=USTECm\n"
    "Period=M15\n"
    "Expert=ORB_Portfolio\n"
    "ExpertParameters=BOTH.set\n"
)
startup_path = DATA / "BOTH_start.ini"
startup_path.write_text(startup, encoding="utf-16")

proc = subprocess.Popen([str(TERMINAL), f"/config:{startup_path}"])
time.sleep(8)
print("pid", proc.pid, "running", proc.poll() is None)
print("risk", args.risk)
print("target", args.target)
print("max_trades", max_trades)
print("set", set_path)
print("startup", startup_path)
