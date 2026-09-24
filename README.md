# Production Planner

Backend-first recipe planning for discrete production systems. It loads a portable SQLite catalog, expands requested outputs into a pooled bill of materials, calculates rolled costs, and creates a deterministic finite-capacity schedule.

## Quick start (Windows)

```powershell
.\scripts\setup.ps1
.\.venv\Scripts\planner.exe db validate --database .\sampledata\hay_day_starter.sqlite
.\.venv\Scripts\planner.exe plan create --database .\sampledata\hay_day_starter.sqlite --output cream_cake=2@1 --output cheesecake=1@2 --save .\work\example-plan.json
.\scripts\launch.ps1 -Database .\sampledata\hay_day_starter.sqlite
```

Open `http://127.0.0.1:8000/docs` for interactive API documentation. To view a saved plan without its source database, run:

```powershell
.\scripts\launch.ps1 -Plan .\work\example-plan.json
```

## Build a database

Copy `sampledata/hay_day_starter.xlsx`, keep the sheet names and header rows, replace the sample rows, and run:

```powershell
.\.venv\Scripts\planner.exe db check-workbook --input .\my-recipes.xlsx
.\.venv\Scripts\planner.exe db build --input .\my-recipes.xlsx --output .\my-recipes.sqlite
```

The build is atomic. Existing targets are refused unless `--force` is explicitly supplied.

## Scheduling policy

Jobs are non-preemptive. Stations run in parallel; identical station instances run independently. A job becomes ready only after all allocated prerequisite batches finish. Ready work is ordered by output priority, longest remaining critical path, request order, then stable job ID. Lower-priority work may use an otherwise idle station while higher-priority work is blocked.

See `vault.md` before changing components.

