from decimal import Decimal

from production_planner.engine import Catalog, Planner, load_plan
from production_planner.schemas import OutputRequest, PlanRequest


def test_pools_intermediate_and_schedules_dependencies(catalog_path):
    request = PlanRequest(
        outputs=[
            OutputRequest(item_key="widget", quantity=Decimal("1"), priority=1),
            OutputRequest(item_key="gadget", quantity=Decimal("1"), priority=2),
        ],
        capacity_profile="default",
    )
    result = Planner(Catalog(catalog_path)).compute(request)
    plate = next(row for row in result.production if row["item_key"] == "plate")
    assert plate["recipe_runs"] == 1
    assert plate["produced_quantity"] == "2"
    assert next(row for row in result.bom if row["item_key"] == "ore")["quantity"] == "3"
    plate_job = next(job for job in result.jobs if job["item_key"] == "plate")
    downstream = [job for job in result.jobs if job["item_key"] in {"widget", "gadget"}]
    assert all(job["start_seconds"] >= plate_job["end_seconds"] for job in downstream)
    assert next(job for job in downstream if job["item_key"] == "widget")["start_seconds"] < next(
        job for job in downstream if job["item_key"] == "gadget"
    )["start_seconds"]
    assert result.actual_input_cost == "6"


def test_multiple_station_override_reduces_finish_time(catalog_path):
    base = PlanRequest(
        outputs=[OutputRequest(item_key="widget", quantity=Decimal("2"), priority=1)],
        capacity_profile="default",
    )
    parallel = base.model_copy(update={"station_overrides": {"bench": 2}})
    single_result = Planner(Catalog(catalog_path)).compute(base)
    parallel_result = Planner(Catalog(catalog_path)).compute(parallel)
    assert parallel_result.overall_completion_seconds < single_result.overall_completion_seconds


def test_plan_round_trip_without_database(catalog_path, tmp_path):
    request = PlanRequest(outputs=[OutputRequest(item_key="widget", quantity=Decimal("1"))], capacity_profile="default")
    result = Planner(Catalog(catalog_path)).compute(request)
    path = tmp_path / "plan.json"
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    loaded = load_plan(path)
    assert loaded.source_database["sha256"]
    assert loaded.outputs == result.outputs

