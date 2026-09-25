# Desktop window and userdata packaging plan

## Current desktop run

`scripts/launch.ps1` now opens a contained native window by default. The window hosts the same loopback-only FastAPI application through pywebview, so planner behavior stays shared with browser mode. Pass `-Browser` only when the API/browser workflow is intentionally needed.

The desktop process selects an available loopback port, starts the local server on a background thread, opens the native window, and stops the server when that window closes. On Windows, pywebview uses the installed WebView2 runtime.

## Userdata location policy

Userdata must never be stored beside a packaged executable. A one-file binary may run from a read-only directory and may unpack itself into a temporary directory that disappears after exit.

The implemented path policy is:

| Runtime | Userdata directory |
| --- | --- |
| Repository/development launch | `<repository>/userdata/` (Git-ignored) |
| Frozen Windows executable | `%LOCALAPPDATA%\ProductionPlanner\userdata` |
| Frozen macOS app | `~/Library/Application Support/ProductionPlanner/userdata` |
| Frozen Linux binary | `$XDG_DATA_HOME/production-planner/userdata`, falling back to `~/.local/share/production-planner/userdata` |
| Explicit deployment override | `PLANNER_USERDATA_DIR` |

Each session remains a separate, timestamped JSON file. Changes are written through a temporary file followed by an atomic replacement. Starting a new session never removes previous files, and importing a userdata file creates a new working copy before later saves.

## Binary packaging plan

1. Add PyInstaller as a build-only dependency and produce a windowed one-file executable from a small entry point that calls `production_planner.desktop.run_desktop()`.
2. Bundle `sampledata/hay_day.sqlite` under `sampledata/` and the `production_planner/static/` package data. `resource_root()` already supports PyInstaller's temporary `_MEIPASS` directory for read-only bundled assets.
3. Include pywebview's platform hook and required data with `--collect-all webview`. Do not bundle userdata or a writable database into the executable.
4. Build with `--windowed` so end users see only the app window. Keep a separate console/debug build for diagnostics.
5. On Windows, have the installer check for the Evergreen WebView2 Runtime and install Microsoft's bootstrapper only when it is absent.
6. Smoke-test the packaged executable from both a writable folder and a read-only installation folder. Confirm that both write to the same per-user application-data directory.
7. Test upgrade behavior by creating userdata with one build, replacing the executable, and confirming that the newer build resumes the unchanged files.
8. Before a userdata schema-major change, add a copy-on-write migrator. Preserve the original file, migrate into a newly named session, and expose a clear error for unsupported newer versions.

## Backup and recovery

The Data tab can load any compatible userdata JSON. A future packaging milestone should add “Open userdata folder” and “Export current userdata” actions. Until then, backups consist of copying the application-data `userdata` directory; no registry entries or executable-relative files are required.
