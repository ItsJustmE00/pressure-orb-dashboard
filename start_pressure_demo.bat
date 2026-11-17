@echo off
echo ========================================
echo PRESSURE ORB DEMO - COMPLETE LAUNCH
echo ========================================
echo.

cd /d c:\Users\moham\Downloads\agency-agents-main\agency-agents-main

echo [1/5] Compiling ORB_Pressure EA...
"C:\Program Files\MetaTrader 5\metaeditor64.exe" /compile /log "mql5\orb_portfolio\ORB_Pressure.mq5"
timeout /t 5

echo.
echo [2/5] Launching MT5 Terminal with Pressure config...
C:\Python314\python.exe tools\launch_pressure_demo.py --risk 0.5 --target 2.0 --max-trades 10 --buy-pressure 0.6 --sell-pressure 0.6 --pressure-bars 3
timeout /t 10

echo.
echo [3/5] Starting Flask Backend...
start "Flask Backend" cmd /k "cd /d c:\Users\moham\Downloads\agency-agents-main\agency-agents-main && C:\Python314\python.exe web\app.py --port 8050"
timeout /t 5

echo.
echo [4/5] Starting Cloudflare Tunnel...
start "Cloudflare Tunnel" cmd /k "cloudflared tunnel --url http://127.0.0.1:8050 --no-autoupdate"
timeout /t 5

echo.
echo [5/5] Opening local dashboard...
start http://127.0.0.1:8050

echo.
echo ========================================
echo LAUNCH COMPLETE
echo ========================================
echo.
echo Dashboard local: http://127.0.0.1:8050
echo.
echo MANUAL STEPS REQUIRED:
echo 1. In MT5, open USTECm M15 chart
echo 2. Attach ORB_Pressure.ex5 to chart
echo 3. Load PRESSURE.set preset
echo 4. Enable Algo Trading
echo 5. Wait for 09:30 NY for first trade
echo.
echo CONFIGURATION:
echo - Risk: 0.5%% per trade
echo - Target: 2R
echo - Max trades/day: 10
echo - Buy pressure threshold: 0.6
echo - Sell pressure threshold: 0.6
echo - Pressure bars: 3
echo.
echo The EA will calculate buyer/seller pressure from candle movements
echo and enter trades when pressure exceeds threshold after range breakout.
echo.
echo ========================================
pause
