# Start the app on Windows:   .\scripts\start.ps1   -> http://localhost:8000
#
# If PowerShell refuses to run this, run this once in the same window first:
#     Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$activate = ".\.venv\Scripts\Activate.ps1"
if (Test-Path $activate) {
  . $activate
} else {
  Write-Host "X No .venv found. Run .\scripts\setup.ps1 first." -ForegroundColor Red
  exit 1
}

$port = if ($env:PORT) { $env:PORT } else { "8000" }
Write-Host "ShipCheck running at http://localhost:$port   (Ctrl+C to stop)" -ForegroundColor Green
python -m uvicorn app.api:app --app-dir src --port $port --reload
