@echo off
echo ============================================
echo COMPILING ORB_Pressure.mq5
echo ============================================
echo.

cd /d "C:\Users\moham\Downloads\agency-agents-main\agency-agents-main"

echo Killing MetaEditor...
taskkill /F /IM metaeditor64.exe 2>nul
timeout /t 2 /nobreak >nul

echo Compiling...
"C:\Program Files\MetaTrader 5\metaeditor64.exe" /compile "mql5\orb_portfolio\ORB_Pressure.mq5" /close

timeout /t 5 /nobreak >nul

echo.
echo Checking for compiled file...
if exist "mql5\orb_portfolio\ORB_Pressure.ex5" (
    echo [OK] ORB_Pressure.ex5 created successfully
) else (
    echo [FAIL] ORB_Pressure.ex5 not found
    echo Please compile manually in MetaEditor
)

echo.
pause
