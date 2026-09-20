# One-time setup on Windows:   .\scripts\setup.ps1
#
# If PowerShell refuses to run this ("running scripts is disabled on this system"),
# run this once in the same window, then try again:
#     Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

# Python 3.10+ — prefer the "py" launcher that the python.org installer adds.
$exe = $null; $pre = @()
if (Get-Command py -ErrorAction SilentlyContinue)          { $exe = "py";     $pre = @("-3") }
elseif (Get-Command python -ErrorAction SilentlyContinue)  { $exe = "python"; $pre = @() }
else {
  Write-Host "X Python not found. Install 3.10 or newer from https://www.python.org/downloads/" -ForegroundColor Red
  Write-Host "  During install, tick 'Add python.exe to PATH', then reopen PowerShell." -ForegroundColor Red
  exit 1
}

$ok = (& $exe @pre -c "import sys; print(sys.version_info >= (3, 10))" 2>$null | Out-String).Trim()
if ($ok -ne "True") {
  Write-Host "X Python 3.10 or newer is needed. Get it from https://www.python.org/downloads/" -ForegroundColor Red
  exit 1
}

Write-Host "-> Creating a private Python environment in .venv"
& $exe @pre -m venv .venv

$activate = ".\.venv\Scripts\Activate.ps1"
if (-not (Test-Path $activate)) {
  Write-Host "X .venv was not created properly. Delete the .venv folder and run this again." -ForegroundColor Red
  exit 1
}
. $activate

Write-Host "-> Installing libraries"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements-dev.txt

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "-> Created .env (add your AI keys later - the app works without them)"
}

Write-Host "-> Processing the 520 sample emails (rules only, takes about a second)"
python scripts/run_batch.py --no-llm | Select-Object -Last 3

Write-Host "-> Running tests"
python -m pytest -q | Select-Object -Last 1

Write-Host ""
Write-Host "OK. Start the app with:  .\scripts\start.ps1" -ForegroundColor Green
