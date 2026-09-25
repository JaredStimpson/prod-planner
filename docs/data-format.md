# Catalog data format

Catalogs are SQLite files created from a workbook. The workbook is the editable source of truth. Version 1.1 accepts either the original planner template or the normalized database workbook used by the bundled Hay Day catalog.

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

The normalized workbook format uses `items`, `production_methods`, `production_components`, `stations`, and `categories`. It may also contain the descriptive `schema` sheet and redundant `item_subitems` flat view. The canonical normalized tables are imported; the flat view is not duplicated in SQLite. The converter maps minutes to seconds and retains:

- category, unlock level, and source URL per item;
- station type;
- output quantity, base time, mastered time, unlock level, and notes per method;
- component quantity and sequence;
- schema metadata, including the source date.

Because the supplied workbook has no average-cost column, each item receives the explicit temporary value `1` with value basis `temporary v1.1 default`. Five currency/reward rows without production methods remain raw inputs. A `hay_day_default` capacity profile is generated with one instance of each station.

The converter validates every row before creating a temporary database, then moves the completed database into place. With `--force`, replacement occurs only after validation and temporary database creation succeed.
