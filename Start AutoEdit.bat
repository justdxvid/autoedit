@echo off
setlocal
cd /d "%~dp0"
echo Starting AutoEdit for FilmCraft...
where py.exe >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    start "" py -3 "%~dp0app.py"
    goto :started
)
where python.exe >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    start "" python "%~dp0app.py"
    goto :started
)
echo [ERROR] Python 3 was not found in your PATH.
echo Please install Python 3 from https://python.org or run 'winget install Python.Python.3.12'.
pause
exit /b 1

:started
echo AutoEdit background server started.
echo The panel will open at http://127.0.0.1:8765 in your default browser.
timeout /t 2 >nul
