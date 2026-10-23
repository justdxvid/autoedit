# AutoEdit Installer for Windows (PowerShell 5.1+)
# Sets up dependencies, motion graphics, CLI commands, and shortcuts.

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Write-Ok($msg)   { Write-Host "  [✓] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [!] $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "  [✗] $msg" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "AutoEdit Installer (Windows)" -ForegroundColor Cyan
Write-Host "============================" -ForegroundColor Cyan
Write-Host ""

$SrcDir = $PSScriptRoot
if (-not $SrcDir) { $SrcDir = Split-Path -Parent $MyInvocation.MyCommand.Path }

$LocalAppData = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
$AppData = [Environment]::GetFolderPath([Environment+SpecialFolder]::ApplicationData)
$Desktop = [Environment]::GetFolderPath([Environment+SpecialFolder]::Desktop)
$StartMenu = [Environment]::GetFolderPath([Environment+SpecialFolder]::Programs)

$AutoEditHome = Join-Path $LocalAppData "AutoEdit"
$BinDir = Join-Path $AutoEditHome "bin"
$ModelsDir = Join-Path $AutoEditHome "models"
$HistoryDir = Join-Path $AppData "AutoEdit\history"
$MusicDir = Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::MyMusic)) "AutoEdit"
$OverlaysDir = Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::MyVideos)) "AutoEdit Overlays"

# Create directories
foreach ($dir in @($AutoEditHome, $BinDir, $ModelsDir, $HistoryDir, $MusicDir, $OverlaysDir)) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}
Write-Ok "AutoEdit data directories initialized"

# 1. Python Check
$PythonExe = $null
if (Get-Command py.exe -ErrorAction SilentlyContinue) {
    $PythonExe = "py -3"
    $pyVer = & py -3 --version 2>&1
    Write-Ok "Python found: $pyVer"
} elseif (Get-Command python.exe -ErrorAction SilentlyContinue) {
    $PythonExe = "python"
    $pyVer = & python --version 2>&1
    Write-Ok "Python found: $pyVer"
} else {
    Write-Warn "Python 3 was not detected in PATH."
    Write-Host "      Install Python 3 from https://python.org or via: winget install Python.Python.3.12" -ForegroundColor Gray
}

# 2. FFmpeg Check
if (Get-Command ffmpeg.exe -ErrorAction SilentlyContinue) {
    $ffVer = (ffmpeg -version 2>&1 | Select-Object -First 1)
    Write-Ok "FFmpeg found: $ffVer"
} else {
    Write-Warn "ffmpeg not found in PATH."
    Write-Host "      Install it via winget: winget install Gyan.FFmpeg" -ForegroundColor Gray
    Write-Host "      or via scoop: scoop install ffmpeg" -ForegroundColor Gray
}

# 3. Node.js & HyperFrames Check
$NodeCmd = Get-Command node.exe -ErrorAction SilentlyContinue
$NpmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $NpmCmd) { $NpmCmd = Get-Command npm.exe -ErrorAction SilentlyContinue }

if ($NodeCmd) {
    $nodeVer = & node --version 2>&1
    Write-Ok "Node.js found: $nodeVer"
    
    $HfDir = Join-Path $SrcDir "hyperframes"
    if (Test-Path (Join-Path $HfDir "package.json")) {
        Write-Host "  [...] Installing HyperFrames motion graphics dependencies..." -ForegroundColor Gray
        try {
            Push-Location $HfDir
            & cmd.exe /c "npm install --silent 2>nul"
            Pop-Location
            Write-Ok "HyperFrames motion graphics ready"
        } catch {
            Pop-Location
            Write-Warn "HyperFrames npm install encountered a warning. You can run 'npm install' inside '$HfDir' manually."
        }
    }
} else {
    Write-Warn "Node.js not detected in PATH."
    Write-Host "      Motion graphics require Node.js 18+. Install via: winget install OpenJS.NodeJS" -ForegroundColor Gray
}

# 4. Whisper Check
$WhisperCmd = Get-Command whisper-cli.exe -ErrorAction SilentlyContinue
if (-not $WhisperCmd) { $WhisperCmd = Get-Command whisper.exe -ErrorAction SilentlyContinue }
if (-not $WhisperCmd) { $WhisperCmd = Get-Command main.exe -ErrorAction SilentlyContinue }

if ($WhisperCmd) {
    Write-Ok "whisper.cpp found: $($WhisperCmd.Source)"
} else {
    Write-Warn "whisper-cli.exe not found in PATH."
    Write-Host "      Speech-to-text uses whisper.cpp. Download a Windows binary from https://github.com/ggml-org/whisper.cpp/releases" -ForegroundColor Gray
    Write-Host "      and place whisper-cli.exe in: $BinDir" -ForegroundColor Gray
}

# 5. FilmCraft CLI Check
$FcCli = Get-Command filmcraft-cli.exe -ErrorAction SilentlyContinue
if (-not $FcCli) { $FcCli = Get-Command filmcraft-cli -ErrorAction SilentlyContinue }

if ($FcCli) {
    Write-Ok "filmcraft-cli found: $($FcCli.Source)"
} else {
    Write-Warn "filmcraft-cli.exe not found in PATH."
    Write-Host "      Download the FilmCraft release from https://github.com/storytold/filmcraft/releases" -ForegroundColor Gray
    Write-Host "      and place filmcraft-cli.exe in: $BinDir" -ForegroundColor Gray
}

# 6. Create CLI wrapper in $BinDir\autoedit.bat
$AutoEditBat = Join-Path $BinDir "autoedit.bat"
$AutoEditScript = Join-Path $SrcDir "autoedit.py"
$BatContent = @"
@echo off
setlocal
where py.exe >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3 "$AutoEditScript" %*
) else (
    python "$AutoEditScript" %*
)
"@
Set-Content -Path $AutoEditBat -Value $BatContent -Encoding ASCII
Write-Ok "CLI command created: $AutoEditBat"

# Also create autoedit.cmd
$AutoEditCmd = Join-Path $BinDir "autoedit.cmd"
Set-Content -Path $AutoEditCmd -Value $BatContent -Encoding ASCII

# Install native FilmCraft extension plugin (%APPDATA%\FilmCraft\plugins\autoedit)
$PluginRunner = Join-Path $SrcDir "plugin_runner.py"
try {
    & $PyCmd $PluginRunner install | Out-Null
} catch {
    $PluginDir = Join-Path $AppData "FilmCraft\plugins\autoedit"
    New-Item -ItemType Directory -Force -Path $PluginDir | Out-Null
    Copy-Item -Path (Join-Path $SrcDir "plugin.json") -Destination (Join-Path $PluginDir "plugin.json") -Force
    Copy-Item -Path (Join-Path $SrcDir "plugin_runner.py") -Destination (Join-Path $PluginDir "plugin_runner.py") -Force
    Set-Content -Path (Join-Path $PluginDir "autoedit_root.txt") -Value $SrcDir -Encoding UTF8 -NoNewline
}
Write-Ok "FilmCraft native plugin installed: Window -> Extensions -> AutoEdit"

# 7. Add $BinDir to User PATH if missing
$UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($UserPath -notlike "*$BinDir*") {
    $NewPath = if ($UserPath) { "$UserPath;$BinDir" } else { $BinDir }
    [Environment]::SetEnvironmentVariable("PATH", $NewPath, "User")
    $env:PATH = "$env:PATH;$BinDir"
    Write-Ok "Added $BinDir to User PATH"
} else {
    Write-Ok "User PATH already includes $BinDir"
}

# 8. Create Desktop and Start Menu Shortcuts for Start AutoEdit
$StartBat = Join-Path $SrcDir "Start AutoEdit.bat"
if (-not (Test-Path $StartBat)) {
    $StartContent = @"
@echo off
setlocal
cd /d "%~dp0"
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
echo Python 3 was not found. Please install Python from https://python.org or winget install Python.Python.3.12
pause
exit /b 1

:started
echo AutoEdit launched in background. Opening http://127.0.0.1:8765 ...
"@
    Set-Content -Path $StartBat -Value $StartContent -Encoding ASCII
}

# Shortcut creation helper using WScript.Shell
try {
    $WshShell = New-Object -ComObject WScript.Shell
    
    # Desktop shortcut
    $DesktopLink = Join-Path $Desktop "AutoEdit.lnk"
    $Shortcut = $WshShell.CreateShortcut($DesktopLink)
    $Shortcut.TargetPath = $StartBat
    $Shortcut.WorkingDirectory = $SrcDir
    $Shortcut.Description = "One-click automated editing panel for FilmCraft"
    $Shortcut.Save()
    Write-Ok "Desktop shortcut created: $DesktopLink"
    
    # Start menu shortcut
    $ProgramsDir = Join-Path $StartMenu "AutoEdit"
    if (-not (Test-Path $ProgramsDir)) { New-Item -ItemType Directory -Path $ProgramsDir -Force | Out-Null }
    $StartMenuLink = Join-Path $ProgramsDir "AutoEdit.lnk"
    $Shortcut2 = $WshShell.CreateShortcut($StartMenuLink)
    $Shortcut2.TargetPath = $StartBat
    $Shortcut2.WorkingDirectory = $SrcDir
    $Shortcut2.Description = "One-click automated editing panel for FilmCraft"
    $Shortcut2.Save()
    Write-Ok "Start Menu shortcut created: $StartMenuLink"
} catch {
    Write-Warn "Could not create Windows desktop shortcuts (non-fatal): $_"
}

Write-Host ""
Write-Host "AutoEdit installation completed successfully!" -ForegroundColor Green
Write-Host "You can start AutoEdit by double-clicking 'Start AutoEdit.bat' or running 'autoedit' in your terminal." -ForegroundColor Cyan
Write-Host ""
