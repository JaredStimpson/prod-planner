from __future__ import annotations

from pathlib import Path

import pytest

from production_planner.database import create_database


@pytest.fixture
def catalog_path(tmp_path: Path) -> Path:
    rows = {
        "metadata": [{"key": "database_name", "value": "Test Factory"}],
        "items": [
            {"item_key": "ore", "name": "Ore", "kind": "raw", "unit": "unit", "average_value": "2", "value_basis": "test", "notes": None},
            {"item_key": "plate", "name": "Plate", "kind": "producible", "unit": "unit", "average_value": "8", "value_basis": "test", "notes": None},
            {"item_key": "widget", "name": "Widget", "kind": "producible", "unit": "unit", "average_value": "30", "value_basis": "test", "notes": None},
            {"item_key": "gadget", "name": "Gadget", "kind": "producible", "unit": "unit", "average_value": "40", "value_basis": "test", "notes": None},
        ],
        "stations": [
            {"station_key": "press", "name": "Press", "notes": None},
            {"station_key": "bench", "name": "Bench", "notes": None},
        ],
        "recipes": [
            {"recipe_key": "make_plate", "output_item_key": "plate", "process_name": "Press plate", "output_quantity": "2", "station_key": "press", "duration_seconds": 10, "is_active": 1, "notes": None},
            {"recipe_key": "make_widget", "output_item_key": "widget", "process_name": "Build widget", "output_quantity": "1", "station_key": "bench", "duration_seconds": 20, "is_active": 1, "notes": None},
            {"recipe_key": "make_gadget", "output_item_key": "gadget", "process_name": "Build gadget", "output_quantity": "1", "station_key": "bench", "duration_seconds": 15, "is_active": 1, "notes": None},
        ],
        "ingredients": [
            {"recipe_key": "make_plate", "item_key": "ore", "quantity": "3"},
            {"recipe_key": "make_widget", "item_key": "plate", "quantity": "1"},
            {"recipe_key": "make_gadget", "item_key": "plate", "quantity": "1"},
        ],
        "capacity_profiles": [{"profile_key": "default", "name": "Default"}],
        "capacities": [
            {"profile_key": "default", "station_key": "press", "station_count": 1},
            {"profile_key": "default", "station_key": "bench", "station_count": 1},
        ],
        "sources": [],
    }
    path = tmp_path / "factory.sqlite"
    create_database(path, rows)
    return path

