param(
    [string]$Database,
    [string]$Plan,
    [int]$Port = 8000
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$planner = Join-Path $root ".venv\Scripts\planner.exe"
if (-not (Test-Path -LiteralPath $planner)) {
    throw "Run scripts\setup.ps1 first."
}
if (($Database -and $Plan) -or (-not $Database -and -not $Plan)) {
    throw "Provide exactly one of -Database or -Plan."
}
if ($Database) { & $planner serve --database $Database --port $Port }
else { & $planner serve --plan $Plan --port $Port }

