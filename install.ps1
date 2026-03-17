# install.ps1 — Install TimeCard on Windows.
# Installs uv if absent, handles WeasyPrint dependencies, then installs the tool.
$ErrorActionPreference = "Stop"

Write-Host "=== TimeCard Installer ==="

# Ensure uv's bin dir (and uv tool binaries) are on Path
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"

# 1. Install uv if not present
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
}

# 2. WeasyPrint on Windows uses GTK3 runtime.
# Check if GTK3 is available; if not, direct the user to install it.
$gtkPath = "C:\Program Files\GTK3-Runtime Win64"
if (-not (Test-Path $gtkPath)) {
    Write-Host ""
    Write-Host "WeasyPrint requires the GTK3 runtime on Windows."
    Write-Host "Download and install it from:"
    Write-Host "  https://github.com/nickvdyck/WeasyPrint-Installer/releases"
    Write-Host ""
    Write-Host "After installing GTK3, re-run this script."
    exit 2
}

# 3. Install timecard
Write-Host "Installing TimeCard..."
uv tool install git+https://github.com/derekmarion/timecard.git

# 4. Install PowerShell completion
Write-Host "Installing PowerShell completion..."
try {
    timecard --install-completion powershell | Out-Null
} catch {
    Write-Host "Note: Could not install completion. Run 'timecard --install-completion' manually."
}

Write-Host ""
Write-Host "Done! Run 'timecard --help' to get started."
