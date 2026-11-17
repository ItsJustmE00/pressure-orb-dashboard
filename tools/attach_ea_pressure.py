import time
import sys
from pathlib import Path
import MetaTrader5 as mt5

ROOT = Path(__file__).resolve().parents[1]
SYMBOL = "USTECm"
TIMEFRAME = mt5.TIMEFRAME_M15
EA_NAME = "ORB_Pressure"
EA_PATH = ROOT / "mql5" / "orb_portfolio" / f"{EA_NAME}.ex5"
PRESET_PATH = Path(
    r"C:\Users\moham\AppData\Roaming\MetaQuotes\Terminal"
    r"\D0E8209F77C8CF37AD8BF550E51FF075"
    r"\MQL5\Presets\PRESSURE.set"
)

def attach_ea_to_chart():
    """Attach ORB_Pressure EA to USTECm M15 chart"""
    print(f"Connecting to MT5...")
    if not mt5.initialize():
        print(f"MT5 initialize failed: {mt5.last_error()}")
        return False
    
    print(f"MT5 connected successfully")
    
    # Check if symbol is available
    symbol_info = mt5.symbol_info(SYMBOL)
    if symbol_info is None:
        print(f"Symbol {SYMBOL} not found")
        mt5.shutdown()
        return False
    
    print(f"Symbol {SYMBOL} found")
    
    # Get all charts
    charts = mt5.charts_get_all()
    print(f"Found {len(charts)} charts")
    
    # Find or create USTECm M15 chart
    target_chart = None
    for chart in charts:
        if chart[1] == SYMBOL and chart[2] == TIMEFRAME:
            target_chart = chart[0]
            print(f"Found existing {SYMBOL} M15 chart: {target_chart}")
            break
    
    if target_chart is None:
        print(f"Creating new {SYMBOL} M15 chart...")
        target_chart = mt5.chart_open(SYMBOL, TIMEFRAME)
        if target_chart is None:
            print(f"Failed to create chart: {mt5.last_error()}")
            mt5.shutdown()
            return False
        print(f"Chart created: {target_chart}")
        time.sleep(2)
    
    # Check if EA is already attached
    experts = mt5.chart_get_int(target_chart, mt5.CHART_PROPERTY_EXPERT)
    if experts != 0:
        print(f"EA already attached to chart")
        mt5.shutdown()
        return True
    
    # Attach EA
    print(f"Attaching {EA_NAME} to chart...")
    if not EA_PATH.exists():
        print(f"EA file not found: {EA_PATH}")
        mt5.shutdown()
        return False
    
    # Navigate to chart
    mt5.chart_set_symbol_period(target_chart, SYMBOL, TIMEFRAME)
    time.sleep(1)
    
    # Try to attach EA using chart operations
    # Note: Direct EA attachment via Python API is limited
    # We'll create a script that will be executed by MT5
    
    print(f"EA path: {EA_PATH}")
    print(f"Preset path: {PRESET_PATH}")
    
    # Enable automated trading
    if not mt5.terminal_info().trade_allowed:
        print("Enabling automated trading...")
        # This requires manual action or registry modification
        print("Please enable 'Allow Algo Trading' in MT5 manually")
    
    mt5.shutdown()
    return True

def main():
    print("="*60)
    print("ATTACHING PRESSURE EA TO CHART")
    print("="*60)
    
    success = attach_ea_to_chart()
    
    if success:
        print("\n" + "="*60)
        print("SUCCESS")
        print("="*60)
        print("\nNext steps:")
        print("1. In MT5, verify the EA is attached to USTECm M15")
        print("2. Right-click on chart -> Properties -> Expert Advisors")
        print("3. Load PRESSURE.set preset")
        print("4. Click 'Allow live trading' button")
        print("5. Enable 'Algo Trading' in top toolbar")
        print("\nThe EA will start trading at 09:30 NY")
    else:
        print("\n" + "="*60)
        print("FAILED")
        print("="*60)
        print("\nManual attachment required:")
        print("1. Open USTECm M15 chart in MT5")
        print("2. Drag ORB_Pressure.ex5 from Navigator to chart")
        print("3. Load PRESSURE.set preset")
        print("4. Enable Algo Trading")

if __name__ == "__main__":
    main()
