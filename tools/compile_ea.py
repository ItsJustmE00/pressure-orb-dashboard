import subprocess
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METAEDITOR = r"C:\Program Files\MetaTrader 5\metaeditor64.exe"

def compile_mql5(source_path, timeout=60):
    """Compile MQL5 file with the correct MetaEditor CLI syntax."""
    print(f"Compiling {source_path}...")

    # Kill existing MetaEditor
    try:
        subprocess.run(["taskkill", "/F", "/IM", "metaeditor64.exe"],
                       capture_output=True, timeout=5)
        time.sleep(2)
    except Exception:
        pass

    log_path = source_path.with_suffix(".compile.log")
    cmd = [
        METAEDITOR,
        f"/compile:{source_path}",
        f"/log:{log_path}",
        "/close",
    ]

    try:
        subprocess.run(cmd, timeout=timeout, capture_output=True)
        time.sleep(1)
    except subprocess.TimeoutExpired:
        print(f"Compilation timed out for {source_path}")
        return False
    except Exception as e:
        print(f"Error compiling {source_path}: {e}")
        return False

    log_text = ""
    for encoding in ("utf-16", "utf-8-sig", "utf-8"):
        try:
            log_text = log_path.read_text(encoding=encoding, errors="ignore")
            if log_text.strip():
                break
        except Exception:
            continue

    if "0 errors" in log_text.lower():
        print("Compilation OK: 0 errors, 0 warnings")
        return True

    tail = "\n".join(log_text.strip().splitlines()[-8:])
    print(f"Compilation failed or log unavailable:\n{tail}")
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
        if success and ex5_path.exists():
            print(f"[OK] {ex5_path.name}")
        else:
            print(f"[FAIL] {ex5_path.name} not created or compilation failed")
    
    print()
    print("If compilation failed, compile manually in MetaEditor:")
    print("1. Open MetaEditor")
    print("2. File -> Open -> select .mq5 file")
    print("3. Press F7 to compile")
    print("4. Close MetaEditor")

if __name__ == "__main__":
    main()
