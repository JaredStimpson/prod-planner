# Public interfaces

## API

- `GET /health`
- `GET /v1/items?query=&producible=`
- `GET /v1/items/{item_key}`
- `GET /v1/stations`
- `GET /v1/capacity-profiles`
- `POST /v1/plans/compute`
- `GET /v1/viewer/plan`
- `POST /v1/tools/databases/convert` using multipart field `file`

A planning request contains `outputs` (`item_key`, positive `quantity`, positive integer `priority`), `capacity_profile`, and optional positive `station_overrides`.

## CLI

- `planner db check-workbook`
- `planner db build`
- `planner db validate`
- `planner catalog search`
- `planner plan create`
- `planner plan inspect`
- `planner serve --database ...` or `planner serve --plan ...`

Plan JSON uses major/minor `schema_version`. Readers accept compatible major versions and ignore additional fields. The document contains all names, values, BOM rows, capacities, jobs, schedule results, source fingerprint, and warnings needed for database-independent display.

