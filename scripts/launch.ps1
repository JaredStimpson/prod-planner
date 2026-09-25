param(
    [string]$Database,
    [string]$Plan,
    [switch]$Browser,
    [int]$Port = 8000
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$planner = Join-Path $root ".venv\Scripts\planner.exe"
if (-not (Test-Path -LiteralPath $planner)) {
    throw "Run scripts\setup.ps1 first."
}
if ($Database -and $Plan) {
    throw "Provide at most one of -Database or -Plan."
}
$catalog = if ($Database) { $Database } else { Join-Path $root "sampledata\hay_day.sqlite" }
if ($Browser) {
    if ($Plan) { & $planner serve --plan $Plan --port $Port }
    else { & $planner serve --database $catalog --port $Port }
} else {
    if ($Plan) { & $planner desktop --plan $Plan }
    else { & $planner desktop --database $catalog }
}
