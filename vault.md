# Production Planner Vault

Search this file first. It records where behavior lives, how components interact, and what must remain true.

## Catalog database and workbook converter

- Purpose: validate legacy planner or normalized database workbooks and create portable SQLite database files atomically.
- Code: `src/production_planner/converter.py`, `src/production_planner/database.py`.
- Interfaces: `planner db check-workbook`, `planner db build`, `planner db validate`, and `POST /v1/tools/databases/convert`.
- Invariants: exact headers for the detected workbook format; stable unique keys; positive quantities; one active recipe per producible item; acyclic active recipe graph; normalized categories/station types/unlock levels/source URLs/mastered times/component order are retained; absent normalized costs explicitly become 1; existing output refused unless `--force`; database major schema must be supported.
- Update path: change workbook columns in `converter.SHEETS`, validation, SQL schema, sample workbook builder, `docs/data-format.md`, and converter tests together.
- Tests: `tests/test_converter.py`, including normalized-workbook preservation coverage.

## BOM, cost, and schedule engine

- Purpose: pool demand, expand whole recipe runs, allocate batches, roll costs, and schedule finite station capacity.
- Code: `src/production_planner/engine.py`; request/result contracts in `schemas.py`.
- Interfaces: `Planner.compute(PlanRequest)`, `POST /v1/plans/compute`, and `planner plan create`.
- Invariants: no material unit is allocated twice; recipe runs are whole; surplus remains visible; raw inputs take no station time; prerequisites finish before consuming jobs start; scheduling order is priority, critical path, request order, stable ID; zero-slack prerequisite/resource paths are marked critical; cost gaps remain null and generate warnings.
- Update path: read `docs/scheduling.md`, update JSON schema behavior and regression tests before changing queue or allocation logic.
- Tests: `tests/test_engine.py`.

## API, CLI, and viewer

- Purpose: expose catalog search, planning, conversion, JSON export, database-independent plan viewing, and the interactive local GUI.
- Code: `src/production_planner/api.py`, `src/production_planner/cli.py`, `src/production_planner/static/`.
- Interfaces: documented in `docs/interfaces.md`; launch through `scripts/launch.ps1`.
- Invariants: database and viewer modes are mutually exclusive, while empty GUI mode is allowed; viewer mode cannot search or compute; a locally uploaded database replaces only the in-memory active catalog; exported plans are self-contained; incompatible major plan versions are rejected; graph stages run left-to-right; identical item jobs within a stage share a counted node; distinct downstream relationships keep distinct edges; critical jobs/edges are red; `F` fits the graph unless focus is in an editable control.
- Tests: `tests/test_interfaces.py`.

## Environment and samples

- Purpose: reproducible development environment and executable sample catalog.
- Files: `pyproject.toml`, `scripts/setup.ps1`, `sampledata/`.
- Invariants: local `.venv`; sample workbook converts without manual edits; generated sample database validates; executable packaging is intentionally deferred.

## Change log

- 2026-09-24: Initialized backend v0.1 with workbook conversion, portable catalogs, pooled BOM/cost planning, deterministic scheduling, FastAPI/CLI access, saved-plan viewer, and Hay Day starter data.
- 2026-09-24: Added v1.1 normalized-workbook import and full Hay Day catalog, extended metadata preservation, dynamic database loading, critical-path annotations, and the interactive staged dependency-graph GUI.
- 2026-09-24: Increased the Outputs sidebar's requested-output typography for compact, readable result scanning.
- 2026-09-24: Fixed graph text selection during pan, stacked duplicate same-stage items with counts and preserved branching edges, and added the `F` fit-view shortcut.
