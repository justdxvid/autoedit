# AutoEdit Uninstaller for Windows (PowerShell)
[CmdletBinding()]
param()

$ErrorActionPreference = "SilentlyContinue"

Write-Host "Uninstalling AutoEdit for Windows..." -ForegroundColor Cyan

$LocalAppData = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
$Desktop = [Environment]::GetFolderPath([Environment+SpecialFolder]::Desktop)
$StartMenu = [Environment]::GetFolderPath([Environment+SpecialFolder]::Programs)

$AutoEditHome = Join-Path $LocalAppData "AutoEdit"
$BinDir = Join-Path $AutoEditHome "bin"

# 1. Remove Desktop and Start Menu Shortcuts
$DesktopLink = Join-Path $Desktop "AutoEdit.lnk"
if (Test-Path $DesktopLink) {
    Remove-Item -Path $DesktopLink -Force
    Write-Host "  [✓] Removed Desktop shortcut" -ForegroundColor Green
}

$StartMenuDir = Join-Path $StartMenu "AutoEdit"
if (Test-Path $StartMenuDir) {
    Remove-Item -Path $StartMenuDir -Recurse -Force
    Write-Host "  [✓] Removed Start Menu folder" -ForegroundColor Green
}

# 2. Remove $BinDir from User PATH
$UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($UserPath -like "*$BinDir*") {
    $Cleaned = ($UserPath -split ';' | Where-Object { $_ -ne $BinDir -and $_ -ne "" }) -join ';'
    [Environment]::SetEnvironmentVariable("PATH", $Cleaned, "User")
    Write-Host "  [✓] Removed $BinDir from User PATH" -ForegroundColor Green
}

# 3. Clean up bin wrappers
if (Test-Path $BinDir) {
    Remove-Item -Path $BinDir -Recurse -Force
    Write-Host "  [✓] Removed $BinDir" -ForegroundColor Green
}

Write-Host ""
Write-Host "AutoEdit uninstalled. Your projects, music and videos were kept." -ForegroundColor Green
Write-Host ""
