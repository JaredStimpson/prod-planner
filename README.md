# Production Planner

Interactive recipe planning for discrete production systems. It loads a portable SQLite catalog, expands requested outputs, calculates rolled costs, creates a deterministic finite-capacity schedule, and displays the result as a staged dependency graph.

## Quick start (Windows)

```powershell
.\scripts\setup.ps1
.\.venv\Scripts\planner.exe db validate --database .\sampledata\hay_day.sqlite
.\scripts\launch.ps1
```

The launch script opens the planner in a contained desktop window. Pass `-Browser` to run the earlier browser/API mode at `http://127.0.0.1:8000`; its API documentation remains at `/docs`. The GUI searches all 418 producible items in the bundled 423-item catalog, accepts station-count overrides, and renders draggable PERT-style stages with cursor zoom, pan, and a red critical path. To view a saved plan in the desktop window, run:

Station-count customizations save automatically into JSON files under the ignored `userdata/` directory. On startup, choose whether to resume the last file or begin a separate session. Older files are retained and can be loaded from the Data tab.

```powershell
.\scripts\launch.ps1 -Plan .\work\example-plan.json
```

See `docs/desktop-packaging.md` for packaged-binary resources, WebView2, and persistent per-user storage.

## Build a database

Use either the legacy planner template or the normalized workbook format documented in `docs/data-format.md`, then run:

```powershell
.\.venv\Scripts\planner.exe db check-workbook --input .\my-recipes.xlsx
.\.venv\Scripts\planner.exe db build --input .\my-recipes.xlsx --output .\my-recipes.sqlite
```

The build is atomic. Existing targets are refused unless `--force` is explicitly supplied.

## Scheduling policy

Jobs are non-preemptive. Stations run in parallel; identical station instances run independently. A job becomes ready only after all allocated prerequisite batches finish. Ready work is ordered by output priority, longest remaining critical path, request order, then stable job ID. Lower-priority work may use an otherwise idle station while higher-priority work is blocked.

See `vault.md` before changing components.
