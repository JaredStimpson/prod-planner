# Scheduling model

The engine builds a demand graph from selected outputs. Requests are ordered by numeric priority (1 is highest), then selection order. Common intermediate demand is pooled. Every active recipe is run a whole number of times, with surplus explicitly reported.

Each recipe run becomes one non-preemptive job on one station instance. Produced batches are allocated in request-priority order to downstream jobs or final requests. A downstream job depends on every upstream batch from which it receives material.

The scheduler advances through completion events. Whenever a station instance is free, it selects ready work using:

1. Lowest numeric priority.
2. Longest remaining downstream critical path.
3. Original request order.
4. Stable job ID.

This is work-conserving: ready lower-priority work can start while higher-priority work is blocked. The result is deterministic but is not represented as a globally optimal makespan.

Plan jobs include their ingredient map and an `is_critical` flag. The displayed critical path follows zero-slack prerequisite and same-station execution links backward from the makespan. The GUI uses those flags for red nodes and edges; it lays dependencies into left-to-right stages independently of schedule time.

Raw items are available at time zero and appear in procurement BOM output. Inventory-on-hand, partial/preemptive recipe runs, alternate-recipe optimization, and station setup/changeover times are outside v0.1.
