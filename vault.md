# Production Planner Vault

Search this file first. It records where behavior lives, how components interact, and what must remain true.

## Catalog database and workbook converter

- Purpose: validate spreadsheet catalogs and create portable SQLite database files atomically.
- Code: `src/production_planner/converter.py`, `src/production_planner/database.py`.
- Interfaces: `planner db check-workbook`, `planner db build`, `planner db validate`, and `POST /v1/tools/databases/convert`.
- Invariants: exact sheet headers; stable unique keys; positive quantities; one active recipe per producible item; acyclic active recipe graph; existing output refused unless `--force`; database major schema must be supported.
- Update path: change workbook columns in `converter.SHEETS`, validation, SQL schema, sample workbook builder, `docs/data-format.md`, and converter tests together.
- Tests: `tests/test_converter.py`.

## BOM, cost, and schedule engine

- Purpose: pool demand, expand whole recipe runs, allocate batches, roll costs, and schedule finite station capacity.
- Code: `src/production_planner/engine.py`; request/result contracts in `schemas.py`.
- Interfaces: `Planner.compute(PlanRequest)`, `POST /v1/plans/compute`, and `planner plan create`.
- Invariants: no material unit is allocated twice; recipe runs are whole; surplus remains visible; raw inputs take no station time; prerequisites finish before consuming jobs start; scheduling order is priority, critical path, request order, stable ID; cost gaps remain null and generate warnings.
- Update path: read `docs/scheduling.md`, update JSON schema behavior and regression tests before changing queue or allocation logic.
- Tests: `tests/test_engine.py`.

## API, CLI, and viewer

- Purpose: expose catalog search, planning, conversion, JSON export, and database-independent plan viewing.
- Code: `src/production_planner/api.py`, `src/production_planner/cli.py`.
- Interfaces: documented in `docs/interfaces.md`; launch through `scripts/launch.ps1`.
- Invariants: one startup mode only; viewer mode cannot search or compute; exported plans are self-contained; incompatible major plan versions are rejected.
- Tests: `tests/test_interfaces.py`.

## Environment and samples

- Purpose: reproducible development environment and executable sample catalog.
- Files: `pyproject.toml`, `scripts/setup.ps1`, `sampledata/`.
- Invariants: local `.venv`; sample workbook converts without manual edits; generated sample database validates; executable packaging is intentionally deferred.

## Change log

- 2026-09-24: Initialized backend v0.1 with workbook conversion, portable catalogs, pooled BOM/cost planning, deterministic scheduling, FastAPI/CLI access, saved-plan viewer, and Hay Day starter data.

