from pathlib import Path

import pytest
from openpyxl import Workbook

from production_planner.converter import SHEETS, convert_workbook, read_workbook
from production_planner.database import validate_database
from production_planner.errors import ValidationError


def _workbook(path: Path, cycle: bool = False):
    workbook = Workbook()
    workbook.remove(workbook.active)
    data = {
        "Metadata": [["database_name", "Fixture"]],
        "Items": [["raw", "Raw", "raw", "unit", 1, "test", None], ["final", "Final", "producible", "unit", 5, "test", None]],
        "Stations": [["machine", "Machine", None]],
        "Recipes": [["make_final", "final", "Make", 1, "machine", 10, 1, None]],
        "Ingredients": [["make_final", "final" if cycle else "raw", 1]],
        "CapacityProfiles": [["default", "Default"]],
        "Capacities": [["default", "machine", 1]],
        "Sources": [["fixture", "Fixture", None, None, None]],
    }
    for name, headers in SHEETS.items():
        sheet = workbook.create_sheet(name)
        sheet.append(headers)
        for row in data[name]:
            sheet.append(row)
    workbook.save(path)


def test_converts_valid_workbook_atomically(tmp_path):
    source, target = tmp_path / "input.xlsx", tmp_path / "output.sqlite"
    _workbook(source)
    convert_workbook(source, target)
    validate_database(target)
    with pytest.raises(ValidationError, match="target already exists"):
        convert_workbook(source, target)
    convert_workbook(source, target, force=True)
    validate_database(target)


def test_rejects_cycle_before_database_creation(tmp_path):
    source, target = tmp_path / "cycle.xlsx", tmp_path / "output.sqlite"
    _workbook(source, cycle=True)
    with pytest.raises(ValidationError, match="cycle"):
        read_workbook(source)
    assert not target.exists()
