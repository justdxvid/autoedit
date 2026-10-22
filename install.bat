@echo off
setlocal
cd /d "%~dp0"
echo Starting AutoEdit installation on Windows...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Installation finished with exit code %ERRORLEVEL%.
    pause
    exit /b %ERRORLEVEL%
)
echo.
pause
