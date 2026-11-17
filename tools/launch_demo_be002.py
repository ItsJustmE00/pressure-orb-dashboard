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

params = {
    "InpRiskPct": "3.0",
    "InpTargetR": "3.0",
    "InpMagic": "20261113",
    "InpRangeHourNY": "9",
    "InpRangeMinuteNY": "30",
    "InpCloseHourNY": "16",
    "InpCloseMinuteNY": "0",
    "InpCloseBufferMinutes": "5",
    "InpFridayCloseBufferMinutes": "10",
    "InpServerGMTOffsetHours": "0",
    "InpSlippagePoints": "30",
    "InpMaxSpreadPoints": "500",
    "InpOneTradePerDay": "true",
    "InpLongOnly": "true",
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
    "InpDebugTrend": "false",
}

set_path = PRESETS / "BE002.set"
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
    "ExpertParameters=BE002.set\n"
)
startup_path = DATA / "BE002_start.ini"
startup_path.write_text(startup, encoding="utf-16")

proc = subprocess.Popen([str(TERMINAL), f"/config:{startup_path}"])
time.sleep(8)
print("pid", proc.pid, "running", proc.poll() is None)
print("set", set_path)
print("startup", startup_path)
