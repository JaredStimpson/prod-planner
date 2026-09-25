from fastapi.testclient import TestClient

from production_planner.api import create_app


def test_api_search_and_compute(catalog_path):
    client = TestClient(create_app(database=catalog_path))
    assert client.get("/").status_code == 200
    assert "Production Planner" in client.get("/").text
    assert client.get("/health").json()["mode"] == "database"
    assert client.get("/v1/items", params={"query": "wid"}).json()[0]["item_key"] == "widget"
    response = client.post("/v1/plans/compute", json={
        "outputs": [{"item_key": "widget", "quantity": "1", "priority": 1}],
        "capacity_profile": "default",
        "station_overrides": {},
    })
    assert response.status_code == 200
    assert response.json()["outputs"][0]["item_key"] == "widget"


def test_viewer_mode_is_read_only(catalog_path, tmp_path):
    compute_client = TestClient(create_app(database=catalog_path))
    plan = compute_client.post("/v1/plans/compute", json={
        "outputs": [{"item_key": "widget", "quantity": "1", "priority": 1}],
        "capacity_profile": "default", "station_overrides": {},
    }).json()
    path = tmp_path / "plan.json"
    import json
    path.write_text(json.dumps(plan), encoding="utf-8")
    viewer = TestClient(create_app(plan=path))
    assert viewer.get("/v1/viewer/plan").status_code == 200
    assert viewer.get("/v1/items").status_code == 404


def test_empty_mode_serves_gui_without_catalog():
    client = TestClient(create_app())
    assert client.get("/health").json()["mode"] == "empty"
    assert client.get("/").status_code == 200
