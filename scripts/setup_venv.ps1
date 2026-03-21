# Creates .venv and installs dependencies with a clean mediapipe wheel.
# Run from repo root:  powershell -ExecutionPolicy Bypass -File scripts\setup_venv.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv)) {
    python -m venv .venv
}

& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip uninstall -y mediapipe 2>$null
python -m pip install --no-cache-dir -r requirements.txt

Write-Host "Done. Activate with:  .\.venv\Scripts\Activate.ps1"
Write-Host "Then:  python run_demo.py"
