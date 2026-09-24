param([string]$Python = "")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $root ".venv"
if (-not $Python) {
    if (Get-Command py -ErrorAction SilentlyContinue) { $Python = "py" }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { $Python = "python" }
    else { throw "Python 3.12 was not found. Pass -Python with the full executable path." }
}
if (-not (Test-Path -LiteralPath $venv)) {
    if ((Split-Path -Leaf $Python) -eq "py" -or $Python -eq "py") {
        & $Python -3.12 -m venv $venv
    } else {
        & $Python -m venv $venv
    }
    if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed." }
}
$venvPython = Join-Path $venv "Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& $venvPython -m pip install -e "${root}[dev]"
if ($LASTEXITCODE -ne 0) { throw "Project dependency installation failed." }
Write-Host "Environment ready: $venv"
