from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask

from . import __version__
from .converter import convert_workbook
from .engine import Catalog, Planner, load_plan
from .errors import PlannerError
from .schemas import PlanRequest


def create_app(database: Path | None = None, plan: Path | None = None) -> FastAPI:
    if (database is None) == (plan is None):
        raise ValueError("choose exactly one startup mode: database or saved plan")
    app = FastAPI(title="Production Planner", version=__version__)
    catalog = Catalog(database) if database else None
    saved_plan = load_plan(plan) if plan else None

    @app.exception_handler(PlannerError)
    async def planner_error_handler(_request, exc: PlannerError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__, "mode": "database" if catalog else "viewer"}

    @app.get("/v1/items")
    def items(query: str = "", producible: bool | None = Query(default=None)):
        if not catalog:
            raise HTTPException(404, "catalog is unavailable in viewer mode")
        return catalog.item_rows(query, producible)

    @app.get("/v1/items/{item_key}")
    def item(item_key: str):
        if not catalog or item_key not in catalog.items:
            raise HTTPException(404, "item not found")
        base = next(row for row in catalog.item_rows() if row["item_key"] == item_key)
        recipe = catalog.recipes.get(item_key)
        base["recipe"] = None if not recipe else {
            "recipe_key": recipe.key, "process_name": recipe.process_name,
            "output_quantity": str(recipe.output_quantity), "duration_seconds": recipe.duration,
            "station_key": recipe.station,
            "ingredients": {key: str(value) for key, value in recipe.ingredients.items()},
        }
        return base

    @app.get("/v1/stations")
    def stations():
        if not catalog:
            raise HTTPException(404, "catalog is unavailable in viewer mode")
        return [{"station_key": key, "name": name} for key, name in sorted(catalog.stations.items())]

    @app.get("/v1/capacity-profiles")
    def capacity_profiles():
        if not catalog:
            raise HTTPException(404, "catalog is unavailable in viewer mode")
        return [{
            "profile_key": key, "name": name, "capacities": catalog.capacities[key]
        } for key, name in sorted(catalog.profiles.items())]

    @app.post("/v1/plans/compute")
    def compute(request: PlanRequest):
        if not catalog:
            raise HTTPException(404, "planning is unavailable in viewer mode")
        return Planner(catalog).compute(request)

    @app.get("/v1/viewer/plan")
    def viewer_plan():
        if not saved_plan:
            raise HTTPException(404, "no saved plan was loaded")
        return saved_plan

    @app.post("/v1/tools/databases/convert")
    async def convert(file: UploadFile = File(...)):
        if not file.filename or not file.filename.lower().endswith(".xlsx"):
            raise HTTPException(422, "upload must be an .xlsx workbook")
        temporary_dir = Path(tempfile.mkdtemp(prefix="planner-convert-"))
        workbook_path = temporary_dir / "input.xlsx"
        database_path = temporary_dir / "catalog.sqlite"
        workbook_path.write_bytes(await file.read())
        try:
            convert_workbook(workbook_path, database_path)
        except Exception:
            __import__("shutil").rmtree(temporary_dir, ignore_errors=True)
            raise
        return FileResponse(
            database_path, media_type="application/vnd.sqlite3", filename="catalog.sqlite",
            background=BackgroundTask(__import__("shutil").rmtree, temporary_dir, ignore_errors=True),
        )

    return app


def app_from_environment() -> FastAPI:
    database = os.getenv("PLANNER_DATABASE")
    plan = os.getenv("PLANNER_PLAN")
    return create_app(Path(database) if database else None, Path(plan) if plan else None)
