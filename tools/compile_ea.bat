@echo off
echo ========================================
echo COMPILING PRESSURE EA - ROBUST METHOD
echo ========================================
echo.

REM Kill any existing MetaEditor instances
taskkill /F /IM metaeditor64.exe >nul 2>&1
timeout /t 2 /nobreak >nul

REM Compile ORB_Pressure
echo [1/2] Compiling ORB_Pressure.mq5...
start /wait "" "C:\Program Files\MetaTrader 5\metaeditor64.exe" /compile /close "mql5\orb_portfolio\ORB_Pressure.mq5"
timeout /t 3 /nobreak >nul

REM Check if compiled
if exist "mql5\orb_portfolio\ORB_Pressure.ex5" (
    echo [OK] ORB_Pressure.ex5 created successfully
) else (
    echo [ERROR] ORB_Pressure.ex5 not found
    echo Trying alternative method...
    "C:\Program Files\MetaTrader 5\metaeditor64.exe" /compile "mql5\orb_portfolio\ORB_Pressure.mq5"
    timeout /t 5 /nobreak >nul
)

REM Compile Open_USTECm_M15 script
echo.
echo [2/2] Compiling Open_USTECm_M15.mq5...
start /wait "" "C:\Program Files\MetaTrader 5\metaeditor64.exe" /compile /close "mql5\Scripts\Open_USTECm_M15.mq5"
timeout /t 3 /nobreak >nul

REM Check if compiled
if exist "mql5\Scripts\Open_USTECm_M15.ex5" (
    echo [OK] Open_USTECm_M15.ex5 created successfully
) else (
    echo [ERROR] Open_USTECm_M15.ex5 not found
)

echo.
echo ========================================
echo COMPILATION COMPLETE
echo ========================================
echo.
echo Checking files:
if exist "mql5\orb_portfolio\ORB_Pressure.ex5" echo [X] ORB_Pressure.ex5
if exist "mql5\Scripts\Open_USTECm_M15.ex5" echo [X] Open_USTECm_M15.ex5
if exist "mql5\orb_portfolio\ORB_Portfolio.ex5" echo [X] ORB_Portfolio.ex5 (backup)
echo.
pause
