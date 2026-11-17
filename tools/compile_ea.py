import subprocess
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METAEDITOR = r"C:\Program Files\MetaTrader 5\metaeditor64.exe"

def compile_mql5(source_path, timeout=30):
    """Compile MQL5 file with timeout"""
    print(f"Compiling {source_path}...")
    
    # Kill existing MetaEditor
    try:
        subprocess.run(["taskkill", "/F", "/IM", "metaeditor64.exe"], 
                      capture_output=True, timeout=5)
        time.sleep(2)
    except:
        pass
    
    # Compile with /close flag
    cmd = [METAEDITOR, "/compile", "/close", str(source_path)]
    
    try:
        result = subprocess.run(cmd, timeout=timeout, capture_output=True)
        time.sleep(3)
        return True
    except subprocess.TimeoutExpired:
        print(f"Compilation timed out for {source_path}")
        return False
    except Exception as e:
        print(f"Error compiling {source_path}: {e}")
        return False

def main():
    print("="*60)
    print("COMPILING PRESSURE EA - PYTHON METHOD")
    print("="*60)
    print()
    
    files_to_compile = [
        ROOT / "mql5" / "orb_portfolio" / "ORB_Pressure.mq5",
        ROOT / "mql5" / "Scripts" / "Open_USTECm_M15.mq5"
    ]
    
    results = []
    
    for source in files_to_compile:
        if not source.exists():
            print(f"[SKIP] {source} not found")
            continue
        
        success = compile_mql5(source)
        results.append((source, success))
    
    print()
    print("="*60)
    print("COMPILATION RESULTS")
    print("="*60)
    print()
    
    for source, success in results:
        ex5_path = source.with_suffix(".ex5")
        if ex5_path.exists():
            print(f"[OK] {ex5_path.name}")
        else:
            print(f"[FAIL] {ex5_path.name} not created")
    
    print()
    print("If compilation failed, compile manually in MetaEditor:")
    print("1. Open MetaEditor")
    print("2. File -> Open -> select .mq5 file")
    print("3. Press F7 to compile")
    print("4. Close MetaEditor")

if __name__ == "__main__":
    main()
