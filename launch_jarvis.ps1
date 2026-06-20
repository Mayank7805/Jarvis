# ─────────────────────────────────────────────
# launch_jarvis.ps1 — Jarvis AI Assistant Launcher
# ─────────────────────────────────────────────

Write-Host ""
Write-Host "  ========================================"
Write-Host "   Starting Jarvis AI Assistant..."
Write-Host "  ========================================"
Write-Host ""

# Navigate to the project directory (handles if script is run from Desktop)
Set-Location $PSScriptRoot
if (Test-Path (Join-Path $PSScriptRoot "Mayank\Project\Jarvis")) {
    Set-Location (Join-Path $PSScriptRoot "Mayank\Project\Jarvis")
}

$projectRoot = $pwd.Path

# Verify the venv exists
$venvPython = Join-Path $projectRoot "venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "  [ERROR] Virtual environment not found at $venvPython" -ForegroundColor Red
    Write-Host "  Please run: python -m venv venv"
    Read-Host "Press Enter to exit"
    exit 1
}

# Verify main.py exists
if (-not (Test-Path "main.py")) {
    Write-Host "  [ERROR] main.py not found in $(Get-Location)" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Start the Python backend in a new window using venv python directly
# (avoids relying on PATH / activate inheritance across Start-Process boundaries)
Write-Host "  [1/2] Launching Python backend..."
Start-Process -FilePath $venvPython -ArgumentList "main.py" -WorkingDirectory $projectRoot -WindowStyle Normal

# Give the backend time to initialise (STT model, server, etc.)
Write-Host "  [...]  Waiting for backend to initialise..."
Start-Sleep -Seconds 8

# Start the UI (Electron / React)
Write-Host "  [2/2] Launching UI..."
$uiDir = Join-Path $projectRoot "ui"
if (-not (Test-Path (Join-Path $uiDir "node_modules"))) {
    Write-Host "  [WARN] node_modules not found — running npm install first..."
    Set-Location $uiDir
    & npm install
} else {
    Set-Location $uiDir
Start-Process npm -ArgumentList "start" -WorkingDirectory $uiDir

Write-Host ""
Write-Host "  Jarvis is starting..."
Write-Host "  (You can close this window)"
Write-Host ""
