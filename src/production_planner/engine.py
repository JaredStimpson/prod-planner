from __future__ import annotations

import json
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from . import __version__
from .database import database_fingerprint, open_database
from .errors import ValidationError
from .schemas import PlanDocument, PlanRequest

PLAN_SCHEMA_VERSION = "1.0"


def _text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def _ceil(value: Decimal) -> int:
    return int(value.to_integral_value(rounding="ROUND_CEILING"))


@dataclass
class Item:
    key: str
    name: str
    kind: str
    unit: str
    average_value: Decimal | None
    value_basis: str | None


@dataclass
class Recipe:
    key: str
    output: str
    process_name: str
    output_quantity: Decimal
    station: str
    duration: int
    ingredients: dict[str, Decimal]


@dataclass
class Demand:
    quantity: Decimal
    priority: int
    order: int
    consumer_job: str | None = None
    request_index: int | None = None


@dataclass
class Job:
    job_id: str
    item_key: str
    recipe_key: str
    station_key: str
    duration: int
    output_quantity: Decimal
    priority: int = 10**9
    request_order: int = 10**9
    dependencies: set[str] = field(default_factory=set)
    start: int | None = None
    end: int | None = None
    station_instance: int | None = None


class Catalog:
    def __init__(self, database: Path):
        self.database = database
        with open_database(database) as connection:
            self.items = {
                row["item_key"]: Item(
                    row["item_key"], row["name"], row["kind"], row["unit"],
                    Decimal(row["average_value"]) if row["average_value"] is not None else None,
                    row["value_basis"],
                )
                for row in connection.execute("SELECT * FROM items ORDER BY name")
            }
            ingredient_rows: dict[str, dict[str, Decimal]] = defaultdict(dict)
            for row in connection.execute("SELECT * FROM ingredients"):
                ingredient_rows[row["recipe_key"]][row["item_key"]] = Decimal(row["quantity"])
            self.recipes = {}
            for row in connection.execute("SELECT * FROM recipes WHERE is_active=1"):
                self.recipes[row["output_item_key"]] = Recipe(
                    row["recipe_key"], row["output_item_key"], row["process_name"],
                    Decimal(row["output_quantity"]), row["station_key"], row["duration_seconds"],
                    ingredient_rows[row["recipe_key"]],
                )
            self.stations = {row["station_key"]: row["name"] for row in connection.execute("SELECT * FROM stations")}
            self.profiles = {
                row["profile_key"]: row["name"] for row in connection.execute("SELECT * FROM capacity_profiles")
            }
            self.capacities: dict[str, dict[str, int]] = defaultdict(dict)
            for row in connection.execute("SELECT * FROM capacities"):
                self.capacities[row["profile_key"]][row["station_key"]] = row["station_count"]
            self.metadata = {row["key"]: row["value"] for row in connection.execute("SELECT * FROM metadata")}

    def item_rows(self, query: str = "", producible: bool | None = None) -> list[dict[str, Any]]:
        needle = query.casefold().strip()
        result = []
        for item in sorted(self.items.values(), key=lambda value: value.name.casefold()):
            if needle and needle not in item.name.casefold() and needle not in item.key.casefold():
                continue
            if producible is not None and (item.kind == "producible") != producible:
                continue
            result.append({
                "item_key": item.key, "name": item.name, "kind": item.kind, "unit": item.unit,
                "average_value": _text(item.average_value), "value_basis": item.value_basis,
            })
        return result


class Planner:
    def __init__(self, catalog: Catalog):
        self.catalog = catalog

    def compute(self, request: PlanRequest) -> PlanDocument:
        if request.capacity_profile not in self.catalog.profiles:
            raise ValidationError(f"unknown capacity profile: {request.capacity_profile}")
        capacities = dict(self.catalog.capacities[request.capacity_profile])
        for station, count in request.station_overrides.items():
            if station not in self.catalog.stations:
                raise ValidationError(f"unknown station override: {station}")
            capacities[station] = count
        for output in request.outputs:
            if output.item_key not in self.catalog.items:
                raise ValidationError(f"unknown output item: {output.item_key}")

        reachable, order = self._reachable_order([output.item_key for output in request.outputs])
        demands: dict[str, list[Demand]] = defaultdict(list)
        for index, output in enumerate(request.outputs):
            demands[output.item_key].append(Demand(output.quantity, output.priority, index, request_index=index))

        jobs: dict[str, Job] = {}
        output_jobs: dict[int, set[str]] = defaultdict(set)
        production: dict[str, dict[str, Any]] = {}
        raw_bom: dict[str, Decimal] = defaultdict(Decimal)

        for item_key in order:
            entries = sorted(demands[item_key], key=lambda value: (value.priority, value.order, value.consumer_job or ""))
            if not entries:
                continue
            item = self.catalog.items[item_key]
            total = sum((entry.quantity for entry in entries), Decimal(0))
            if item.kind == "raw":
                raw_bom[item_key] += total
                continue
            recipe = self.catalog.recipes.get(item_key)
            if not recipe:
                raise ValidationError(f"producible item {item_key} has no active recipe")
            if recipe.station not in capacities:
                raise ValidationError(f"capacity profile has no count for station {recipe.station}")
            run_count = _ceil(total / recipe.output_quantity)
            item_jobs: list[Job] = []
            for number in range(run_count):
                job = Job(
                    job_id=f"{item_key}:{number + 1}", item_key=item_key, recipe_key=recipe.key,
                    station_key=recipe.station, duration=recipe.duration, output_quantity=recipe.output_quantity,
                )
                jobs[job.job_id] = job
                item_jobs.append(job)

            entry_index = 0
            remaining_entry = entries[0].quantity
            for job in item_jobs:
                remaining_batch = recipe.output_quantity
                while remaining_batch > 0 and entry_index < len(entries):
                    entry = entries[entry_index]
                    amount = min(remaining_batch, remaining_entry)
                    job.priority = min(job.priority, entry.priority)
                    job.request_order = min(job.request_order, entry.order)
                    if entry.consumer_job:
                        jobs[entry.consumer_job].dependencies.add(job.job_id)
                    if entry.request_index is not None:
                        output_jobs[entry.request_index].add(job.job_id)
                    remaining_batch -= amount
                    remaining_entry -= amount
                    if remaining_entry == 0:
                        entry_index += 1
                        if entry_index < len(entries):
                            remaining_entry = entries[entry_index].quantity
                if job.priority == 10**9:
                    job.priority = entries[-1].priority
                    job.request_order = entries[-1].order
                for ingredient_key, quantity in recipe.ingredients.items():
                    demands[ingredient_key].append(
                        Demand(quantity, job.priority, job.request_order, consumer_job=job.job_id)
                    )
            production[item_key] = {
                "item_key": item_key,
                "name": item.name,
                "required_quantity": _text(total),
                "recipe_runs": run_count,
                "produced_quantity": _text(recipe.output_quantity * run_count),
                "surplus_quantity": _text(recipe.output_quantity * run_count - total),
                "station_key": recipe.station,
                "station_name": self.catalog.stations[recipe.station],
                "duration_per_run_seconds": recipe.duration,
                "average_value": _text(item.average_value),
                "value_basis": item.value_basis,
            }

        schedule = self._schedule(jobs, capacities)
        warnings: list[str] = []
        rolled_cache: dict[str, Decimal | None] = {}
        for item_key, row in production.items():
            row["rolled_cost_per_unit"] = _text(self._rolled_cost(item_key, rolled_cache, warnings))
        bom_rows = []
        actual_cost: Decimal | None = Decimal(0)
        for item_key, quantity in sorted(raw_bom.items(), key=lambda pair: self.catalog.items[pair[0]].name.casefold()):
            item = self.catalog.items[item_key]
            extended = None if item.average_value is None else item.average_value * quantity
            if extended is None:
                actual_cost = None
                warnings.append(f"Missing average/reference value for raw item {item.name}; total cost is incomplete.")
            elif actual_cost is not None:
                actual_cost += extended
            bom_rows.append({
                "item_key": item.key, "name": item.name, "quantity": _text(quantity), "unit": item.unit,
                "average_value": _text(item.average_value), "value_basis": item.value_basis,
                "extended_cost": _text(extended),
            })

        output_rows = []
        for index, output in enumerate(request.outputs):
            related = output_jobs[index]
            completion = max((jobs[job_id].end or 0 for job_id in related), default=0)
            item = self.catalog.items[output.item_key]
            output_rows.append({
                "item_key": item.key, "name": item.name, "quantity": _text(output.quantity),
                "priority": output.priority, "request_order": index,
                "completion_seconds": completion,
                "average_value": _text(item.average_value), "value_basis": item.value_basis,
                "rolled_cost_per_unit": _text(self._rolled_cost(item.key, rolled_cache, warnings)),
            })

        makespan = max((job.end or 0 for job in jobs.values()), default=0)
        station_summary = []
        for station_key, count in sorted(capacities.items()):
            station_jobs = [job for job in jobs.values() if job.station_key == station_key]
            busy = sum(job.duration for job in station_jobs)
            station_summary.append({
                "station_key": station_key,
                "station_name": self.catalog.stations.get(station_key, station_key),
                "station_count": count,
                "busy_seconds": busy,
                "utilization": str((Decimal(busy) / Decimal(makespan * count)).quantize(Decimal("0.0001"))) if makespan else "0",
                "job_count": len(station_jobs),
            })

        job_rows = [{
            "job_id": job.job_id, "item_key": job.item_key, "item_name": self.catalog.items[job.item_key].name,
            "recipe_key": job.recipe_key, "station_key": job.station_key,
            "station_name": self.catalog.stations[job.station_key], "station_instance": job.station_instance,
            "priority": job.priority, "request_order": job.request_order,
            "start_seconds": job.start, "end_seconds": job.end, "duration_seconds": job.duration,
            "output_quantity": _text(job.output_quantity), "dependencies": sorted(job.dependencies),
        } for job in sorted(jobs.values(), key=lambda value: (value.start or 0, value.station_key, value.job_id))]

        source = {
            "name": self.catalog.metadata.get("database_name", self.catalog.database.stem),
            "path_hint": self.catalog.database.name,
            "sha256": database_fingerprint(self.catalog.database),
            "schema_version": self.catalog.metadata.get("schema_version", "unknown"),
        }
        return PlanDocument(
            schema_version=PLAN_SCHEMA_VERSION,
            engine_version=__version__,
            generated_at=datetime.now(timezone.utc).isoformat(),
            source_database=source,
            request=json.loads(request.model_dump_json()),
            capacities=capacities,
            bom=bom_rows,
            production=[production[key] for key in order if key in production],
            outputs=output_rows,
            jobs=job_rows,
            station_summary=station_summary,
            overall_completion_seconds=makespan,
            actual_input_cost=_text(actual_cost),
            warnings=sorted(set(warnings)),
        )

    def _reachable_order(self, roots: list[str]) -> tuple[set[str], list[str]]:
        reachable: set[str] = set()
        edges: dict[str, set[str]] = defaultdict(set)
        queue = list(roots)
        while queue:
            item_key = queue.pop()
            if item_key in reachable:
                continue
            reachable.add(item_key)
            recipe = self.catalog.recipes.get(item_key)
            if recipe:
                for ingredient in recipe.ingredients:
                    edges[item_key].add(ingredient)
                    queue.append(ingredient)
        indegree = {key: 0 for key in reachable}
        for parent, children in edges.items():
            for child in children:
                if child in indegree:
                    indegree[child] += 1
        ready = deque(sorted(key for key, degree in indegree.items() if degree == 0))
        order: list[str] = []
        while ready:
            key = ready.popleft()
            order.append(key)
            for child in sorted(edges[key]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
        if len(order) != len(reachable):
            raise ValidationError("recipe graph contains a cycle")
        return reachable, order

    def _rolled_cost(self, item_key: str, cache: dict[str, Decimal | None], warnings: list[str]) -> Decimal | None:
        if item_key in cache:
            return cache[item_key]
        item = self.catalog.items[item_key]
        if item.kind == "raw":
            cache[item_key] = item.average_value
            return item.average_value
        recipe = self.catalog.recipes[item_key]
        total = Decimal(0)
        for ingredient, quantity in recipe.ingredients.items():
            cost = self._rolled_cost(ingredient, cache, warnings)
            if cost is None:
                cache[item_key] = None
                warnings.append(f"Rolled cost for {item.name} is unavailable because an input value is missing.")
                return None
            total += cost * quantity
        cache[item_key] = total / recipe.output_quantity
        return cache[item_key]

    def _schedule(self, jobs: dict[str, Job], capacities: dict[str, int]) -> list[Job]:
        dependents: dict[str, set[str]] = defaultdict(set)
        for job in jobs.values():
            for dependency in job.dependencies:
                dependents[dependency].add(job.job_id)
        critical_cache: dict[str, int] = {}
        def critical(job_id: str) -> int:
            if job_id not in critical_cache:
                critical_cache[job_id] = jobs[job_id].duration + max(
                    (critical(child) for child in dependents[job_id]), default=0
                )
            return critical_cache[job_id]
        for job_id in jobs:
            critical(job_id)

        machines = {
            station: [{"instance": index + 1, "job": None} for index in range(count)]
            for station, count in capacities.items()
        }
        unscheduled = set(jobs)
        completed: set[str] = set()
        running: list[tuple[int, str]] = []
        now = 0
        while unscheduled or running:
            just_finished = [job_id for end, job_id in running if end <= now]
            if just_finished:
                completed.update(just_finished)
                running = [(end, job_id) for end, job_id in running if end > now]
                for station_machines in machines.values():
                    for machine in station_machines:
                        if machine["job"] in just_finished:
                            machine["job"] = None
            assigned = False
            for station, station_machines in machines.items():
                for machine in station_machines:
                    if machine["job"] is not None:
                        continue
                    candidates = [
                        jobs[job_id] for job_id in unscheduled
                        if jobs[job_id].station_key == station and jobs[job_id].dependencies <= completed
                    ]
                    if not candidates:
                        continue
                    job = min(candidates, key=lambda value: (
                        value.priority, -critical_cache[value.job_id], value.request_order, value.job_id
                    ))
                    job.start = now
                    job.end = now + job.duration
                    job.station_instance = int(machine["instance"])
                    machine["job"] = job.job_id
                    running.append((job.end, job.job_id))
                    unscheduled.remove(job.job_id)
                    assigned = True
            if not assigned:
                if not running and unscheduled:
                    blocked = ", ".join(sorted(unscheduled))
                    raise ValidationError(f"scheduler deadlock; blocked jobs: {blocked}")
                if running:
                    now = min(end for end, _ in running)
        return list(jobs.values())


def load_plan(path: Path) -> PlanDocument:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        version = str(data.get("schema_version", "0"))
        if version.split(".")[0] != PLAN_SCHEMA_VERSION.split(".")[0]:
            raise ValidationError(f"unsupported plan schema version: {version}")
        return PlanDocument.model_validate(data)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        if isinstance(exc, ValidationError):
            raise
        raise ValidationError(f"invalid saved plan: {exc}") from exc

