import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = Path(
    r"C:\Users\moham\AppData\Roaming\MetaQuotes\Terminal"
    r"\D0E8209F77C8CF37AD8BF550E51FF075"
)
PRESET_PATH = DATA_PATH / "MQL5" / "Presets" / "PRESSURE.set"
SYMBOL = "USTECm"
MAGIC = 20261117

DEFAULT_CONFIG = {
    "InpRiskPct": 0.5,
    "InpTargetR": 2.0,
    "InpMagic": MAGIC,
    "InpRangeHourNY": 9,
    "InpRangeMinuteNY": 30,
    "InpCloseHourNY": 23,
    "InpCloseMinuteNY": 0,
    "InpCloseBufferMinutes": 5,
    "InpFridayCloseBufferMinutes": 10,
    "InpServerGMTOffsetHours": 0,
    "InpSlippagePoints": 30,
    "InpMaxSpreadPoints": 500,
    "InpOneTradePerDay": False,
    "InpMaxTradesPerDay": 10,
    "InpMinPressureBars": 3,
    "InpBuyPressureMin": 0.6,
    "InpSellPressureMin": 0.6,
    "InpShowDashboard": True,
    "InpDashX": 12,
    "InpDashY": 24,
    "InpDashFontSize": 9,
}


def write_preset(config):
    PRESET_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for key, value in config.items():
        if isinstance(value, bool):
            value = "true" if value else "false"
        elif isinstance(value, str):
            value = f'"{value}"'
        else:
            value = str(value)
        lines.append(f"{key}={value}")
    PRESET_PATH.write_text("\n".join(lines), encoding="utf-16")
    print(f"Preset written to {PRESET_PATH}")


def terminal_is_running():
    """Evite de lancer un 2e terminal : MT5 doit rester mono-instance."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq terminal64.exe"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return "terminal64.exe" in (result.stdout or "").lower()
    except Exception:
        return False


def launch_terminal():
    terminal_path = Path(r"C:\Program Files\MetaTrader 5\terminal64.exe")
    if not terminal_path.exists():
        terminal_path = Path(r"C:\Program Files (x86)\MetaTrader 5\terminal64.exe")

    if not terminal_path.exists():
        print("ERROR: MT5 terminal not found")
        sys.exit(1)

    if terminal_is_running():
        print("MT5 already running -> no second instance launched.")
        return

    start_ini = DATA_PATH / "PRESSURE_start.ini"
    cmd = [str(terminal_path)]
    if start_ini.exists():
        cmd.append(f"/config:{start_ini}")
        print(f"Launching MT5 terminal with config: {start_ini}")
    else:
        print(f"WARNING: {start_ini} not found, launching without auto-attach")
        print(f"Launching MT5 terminal: {terminal_path}")
    subprocess.Popen(cmd)


def main():
    parser = argparse.ArgumentParser(description="Launch Pressure ORB Demo")
    parser.add_argument("--risk", type=float, default=0.5, help="Risk per trade in percent")
    parser.add_argument("--target", type=float, default=2.0, help="Target R multiple")
    parser.add_argument("--max-trades", type=int, default=10, help="Max trades per day")
    parser.add_argument("--buy-pressure", type=float, default=0.6, help="Buy pressure threshold")
    parser.add_argument("--sell-pressure", type=float, default=0.6, help="Sell pressure threshold")
    parser.add_argument("--pressure-bars", type=int, default=3, help="Number of bars for pressure calc")
    
    args = parser.parse_args()
    
    config = DEFAULT_CONFIG.copy()
    config["InpRiskPct"] = args.risk
    config["InpTargetR"] = args.target
    config["InpMaxTradesPerDay"] = args.max_trades
    config["InpBuyPressureMin"] = args.buy_pressure
    config["InpSellPressureMin"] = args.sell_pressure
    config["InpMinPressureBars"] = args.pressure_bars
    
    write_preset(config)
    launch_terminal()
    
    print("\n" + "="*60)
    print("PRESSURE ORB DEMO LAUNCHED")
    print("="*60)
    print(f"Risk: {args.risk}%")
    print(f"Target: {args.target}R")
    print(f"Max trades/day: {args.max_trades}")
    print(f"Buy pressure threshold: {args.buy_pressure}")
    print(f"Sell pressure threshold: {args.sell_pressure}")
    print(f"Pressure bars: {args.pressure_bars}")
    print(f"Symbol: {SYMBOL}")
    print(f"Magic: {MAGIC}")
    print("\nNext steps:")
    print("1. Wait for MT5 to open")
    print("2. Open USTECm M15 chart")
    print("3. Attach ORB_Pressure.ex5")
    print("4. Load PRESSURE.set preset")
    print("5. Enable Algo Trading")
    print("="*60)


if __name__ == "__main__":
    main()
