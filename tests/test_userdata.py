import json

from fastapi.testclient import TestClient

from production_planner.api import create_app
from production_planner import userdata
from production_planner.userdata import UserDataStore


def test_new_session_preserves_previous_file(tmp_path):
    store = UserDataStore(tmp_path / "userdata")
    first = store.start(use_last=False)
    store.save({"station_bench": 3}, {"database_name": "Fixture"})
    second = store.start(use_last=False)

    assert first["file_name"] != second["file_name"]
    assert len(list((tmp_path / "userdata").glob("userdata-*.json"))) == 2


def test_api_resumes_and_loads_userdata(catalog_path, tmp_path):
    directory = tmp_path / "userdata"
    client = TestClient(create_app(database=catalog_path, userdata_dir=directory))
    assert client.get("/v1/userdata/status").json()["has_last"] is False

    started = client.post("/v1/userdata/session", json={"use_last": False}).json()
    saved = client.post("/v1/userdata/save", json={"station_counts": {"bench": 4, "press": 2}}).json()
    assert saved["file_name"] == started["file_name"]
    assert saved["station_counts"]["bench"] == 4

    resumed_client = TestClient(create_app(database=catalog_path, userdata_dir=directory))
    status = resumed_client.get("/v1/userdata/status").json()
    assert status["has_last"] is True
    resumed = resumed_client.post("/v1/userdata/session", json={"use_last": True}).json()
    assert resumed["station_counts"] == {"bench": 4, "press": 2}

    imported = {
        "schema_version": "1.0",
        "created_at": "2026-09-24T00:00:00+00:00",
        "updated_at": "2026-09-24T00:00:00+00:00",
        "catalog": {},
        "station_counts": {"bench": 7},
    }
    response = resumed_client.post(
        "/v1/userdata/load",
        files={"file": ("saved-userdata.json", json.dumps(imported), "application/json")},
    )
    assert response.status_code == 200
    assert response.json()["station_counts"] == {"bench": 7}
    assert response.json()["file_name"] != resumed["file_name"]


def test_frozen_windows_userdata_uses_local_app_data(monkeypatch, tmp_path):
    monkeypatch.setattr(userdata.sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    monkeypatch.delenv("PLANNER_USERDATA_DIR", raising=False)

    assert userdata.default_userdata_directory() == tmp_path / "LocalAppData" / "ProductionPlanner" / "userdata"
