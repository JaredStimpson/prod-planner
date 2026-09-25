from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from . import __version__
from .converter import convert_workbook
from .engine import Catalog, Planner, load_plan
from .errors import PlannerError
from .schemas import PlanRequest, UserDataSaveRequest, UserDataSessionRequest
from .userdata import UserDataStore


def create_app(database: Path | None = None, plan: Path | None = None, userdata_dir: Path | None = None) -> FastAPI:
    if database is not None and plan is not None:
        raise ValueError("choose at most one startup mode: database or saved plan")
    app = FastAPI(title="Production Planner", version=__version__)
    state = {
        "catalog": Catalog(database) if database else None,
        "saved_plan": load_plan(plan) if plan else None,
        "loaded_directory": None,
        "userdata": UserDataStore(userdata_dir),
    }
    static_dir = Path(__file__).with_name("static")
    app.mount("/assets", StaticFiles(directory=static_dir), name="assets")

    @app.exception_handler(PlannerError)
    async def planner_error_handler(_request, exc: PlannerError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/health")
    def health():
        mode = "database" if state["catalog"] else "viewer" if state["saved_plan"] else "empty"
        return {"status": "ok", "version": __version__, "mode": mode}

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(static_dir / "index.html")

    @app.get("/v1/items")
    def items(query: str = "", producible: bool | None = Query(default=None)):
        catalog = state["catalog"]
        if not catalog:
            raise HTTPException(404, "catalog is unavailable in viewer mode")
        return catalog.item_rows(query, producible)

    @app.get("/v1/items/{item_key}")
    def item(item_key: str):
        catalog = state["catalog"]
        if not catalog or item_key not in catalog.items:
            raise HTTPException(404, "item not found")
        base = next(row for row in catalog.item_rows() if row["item_key"] == item_key)
        recipe = catalog.recipes.get(item_key)
        base["recipe"] = None if not recipe else {
            "recipe_key": recipe.key, "process_name": recipe.process_name,
            "output_quantity": str(recipe.output_quantity), "duration_seconds": recipe.duration,
            "station_key": recipe.station,
            "ingredients": {key: str(value) for key, value in recipe.ingredients.items()},
            "mastered_duration_seconds": recipe.mastered_duration,
            "unlock_level": recipe.unlock_level,
        }
        return base

    @app.get("/v1/stations")
    def stations():
        catalog = state["catalog"]
        if not catalog:
            raise HTTPException(404, "catalog is unavailable in viewer mode")
        return [{"station_key": key, "name": name, "station_type": catalog.station_types.get(key)} for key, name in sorted(catalog.stations.items())]

    @app.get("/v1/capacity-profiles")
    def capacity_profiles():
        catalog = state["catalog"]
        if not catalog:
            raise HTTPException(404, "catalog is unavailable in viewer mode")
        return [{
            "profile_key": key, "name": name, "capacities": catalog.capacities[key]
        } for key, name in sorted(catalog.profiles.items())]

    @app.post("/v1/plans/compute")
    def compute(request: PlanRequest):
        catalog = state["catalog"]
        if not catalog:
            raise HTTPException(404, "planning is unavailable in viewer mode")
        return Planner(catalog).compute(request)

    @app.get("/v1/viewer/plan")
    def viewer_plan():
        saved_plan = state["saved_plan"]
        if not saved_plan:
            raise HTTPException(404, "no saved plan was loaded")
        return saved_plan

    @app.get("/v1/userdata/status")
    def userdata_status():
        return state["userdata"].status()

    @app.post("/v1/userdata/session")
    def userdata_session(request: UserDataSessionRequest):
        return state["userdata"].start(request.use_last)

    @app.post("/v1/userdata/save")
    def userdata_save(request: UserDataSaveRequest):
        catalog = state["catalog"]
        catalog_identity = {} if not catalog else {
            "database_name": catalog.metadata.get("database_name", catalog.database.stem),
            "data_as_of": catalog.metadata.get("data_as_of"),
        }
        return state["userdata"].save(request.station_counts, catalog_identity)

    @app.post("/v1/userdata/load")
    async def userdata_load(file: UploadFile = File(...)):
        if not file.filename or Path(file.filename).suffix.lower() != ".json":
            raise HTTPException(422, "upload must be a userdata JSON file")
        return state["userdata"].load(await file.read())

    @app.post("/v1/catalog/load")
    async def load_database(file: UploadFile = File(...)):
        if not file.filename or Path(file.filename).suffix.lower() not in {".sqlite", ".sqlite3", ".db"}:
            raise HTTPException(422, "upload must be a SQLite database")
        temporary_dir = Path(tempfile.mkdtemp(prefix="planner-catalog-"))
        database_path = temporary_dir / "catalog.sqlite"
        database_path.write_bytes(await file.read())
        try:
            catalog = Catalog(database_path)
        except Exception:
            __import__("shutil").rmtree(temporary_dir, ignore_errors=True)
            raise
        old_directory = state["loaded_directory"]
        state["catalog"] = catalog
        state["saved_plan"] = None
        state["loaded_directory"] = temporary_dir
        if old_directory:
            __import__("shutil").rmtree(old_directory, ignore_errors=True)
        return {
            "name": catalog.metadata.get("database_name", file.filename),
            "items": len(catalog.items), "stations": len(catalog.stations),
        }

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
