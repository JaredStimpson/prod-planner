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
- `POST /v1/catalog/load` using multipart field `file`
- `GET /v1/userdata/status`
- `POST /v1/userdata/session` with `use_last`
- `POST /v1/userdata/save` with `station_counts`
- `POST /v1/userdata/load` using multipart field `file`

`GET /` serves the local planner GUI. It has Data, Capacity, and Outputs panels; database and saved-plan loading; workbook conversion; JSON saving; searchable outputs; per-station counts; and a draggable, pannable, cursor-zoomed dependency graph with stage bands and a red critical path. Repeated jobs for the same item and stage are stacked into one counted node while distinct downstream relationships retain separate edges. Press `F` outside an input to fit the graph. The app may start without a catalog so one can be loaded from the Data panel.

Station-count changes are automatically written to the active JSON session in the ignored `userdata/` directory. At database-mode startup, the GUI offers to resume the most recently updated session or create a new file without deleting earlier sessions. Loading a userdata JSON from the Data panel validates it and creates a new working copy, so the selected source file remains untouched.

A planning request contains `outputs` (`item_key`, positive `quantity`, positive integer `priority`), `capacity_profile`, and optional positive `station_overrides`.

## CLI

- `planner db check-workbook`
- `planner db build`
- `planner db validate`
- `planner catalog search`
- `planner plan create`
- `planner plan inspect`
- `planner serve`, `planner serve --database ...`, or `planner serve --plan ...`

Plan JSON uses major/minor `schema_version`. Readers accept compatible major versions and ignore additional fields. The document contains all names, values, BOM rows, capacities, jobs, schedule results, source fingerprint, and warnings needed for database-independent display.
