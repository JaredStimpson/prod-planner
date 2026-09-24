# Catalog data format

Catalogs are SQLite files created from a workbook. The workbook is the editable source of truth.

Required sheets and columns:

- `Metadata`: `key`, `value`
- `Items`: `item_key`, `name`, `kind`, `unit`, `average_value`, `value_basis`, `notes`
- `Stations`: `station_key`, `name`, `notes`
- `Recipes`: `recipe_key`, `output_item_key`, `process_name`, `output_quantity`, `station_key`, `duration_seconds`, `is_active`, `notes`
- `Ingredients`: `recipe_key`, `item_key`, `quantity`
- `CapacityProfiles`: `profile_key`, `name`
- `Capacities`: `profile_key`, `station_key`, `station_count`
- `Sources`: `source_key`, `title`, `url`, `accessed_date`, `notes`

Keys are stable text identifiers. `kind` is `raw` or `producible`. Quantities and values use decimal numbers. Durations are non-negative whole seconds. Counts are positive integers. Blank optional values remain null; missing values never silently become zero.

The converter validates every row before creating a temporary database, then moves the completed database into place. With `--force`, replacement occurs only after validation and temporary database creation succeed.

