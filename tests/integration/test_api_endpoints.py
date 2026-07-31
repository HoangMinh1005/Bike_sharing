import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_root_endpoint():
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert "message" in data
    assert data["version"] == "1.0.0"


def test_api_health_endpoint():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    json_data = res.json()
    assert "data" in json_data
    assert json_data["data"]["status"] == "ok"
    assert json_data["data"]["database"] == "ok"


def test_system_latest_endpoint():
    res = client.get("/api/v1/system/latest")
    assert res.status_code == 200
    json_data = res.json()
    assert "data" in json_data
    assert "summary_date" in json_data["data"]


def test_system_daily_endpoint():
    # Invalid date format
    res = client.get("/api/v1/system/daily?start_date=invalid&end_date=2026-07-27")
    assert res.status_code == 400
    err = res.json()
    assert "error" in err
    assert err["error"]["code"] == "BAD_REQUEST"

    # Start date > end date
    res = client.get("/api/v1/system/daily?start_date=2026-07-28&end_date=2026-07-20")
    assert res.status_code == 400

    # Valid range
    res = client.get("/api/v1/system/daily?start_date=2026-07-20&end_date=2026-07-27")
    assert res.status_code == 200
    json_data = res.json()
    assert "data" in json_data


def test_stations_daily_endpoint():
    res = client.get("/api/v1/stations/daily?summary_date=2026-07-24&limit=5")
    assert res.status_code == 200
    json_data = res.json()
    assert "data" in json_data
    assert "meta" in json_data
    assert json_data["meta"]["limit"] == 5


def test_stations_search_endpoint():
    res = client.get("/api/v1/stations/search?q=station&limit=5")
    assert res.status_code == 200
    json_data = res.json()
    assert "data" in json_data


def test_regions_daily_endpoint():
    res = client.get("/api/v1/regions/daily?summary_date=2026-07-24&limit=5")
    assert res.status_code == 200
    json_data = res.json()
    assert "data" in json_data
    assert "meta" in json_data


def test_ranking_stations_endpoint():
    res = client.get("/api/v1/ranking/stations?ranking_date=2026-07-24&top_n=5")
    assert res.status_code == 200
    json_data = res.json()
    assert "data" in json_data


def test_pipelines_health_latest_endpoint():
    res = client.get("/api/v1/pipelines/health/latest")
    assert res.status_code == 200
    json_data = res.json()
    assert "data" in json_data
    assert isinstance(json_data["data"], list)


def test_pipelines_runs_latest_endpoint():
    res = client.get("/api/v1/pipelines/runs/latest")
    assert res.status_code == 200
    json_data = res.json()
    assert "data" in json_data


def test_pipelines_health_status_validation():
    # Invalid status should return HTTP 400
    res = client.get("/api/v1/pipelines/health/status/INVALID_STATUS")
    assert res.status_code == 400
    err = res.json()
    assert err["error"]["code"] == "BAD_REQUEST"

    # Valid status
    res = client.get("/api/v1/pipelines/health/status/HEALTHY")
    assert res.status_code == 200
    assert "data" in res.json()


def test_demand_category_validation():
    # Invalid demand category should return HTTP 400
    res = client.get("/api/v1/stations/daily?summary_date=2026-07-24&demand_category=SUPER_HIGH")
    assert res.status_code == 400
    err = res.json()
    assert err["error"]["code"] == "BAD_REQUEST"

    # Valid demand category
    res = client.get("/api/v1/stations/daily?summary_date=2026-07-24&demand_category=HIGH")
    assert res.status_code == 200

    # Valid in ranking endpoint
    res = client.get("/api/v1/ranking/stations?ranking_date=2026-07-24&demand_category=LOW")
    assert res.status_code == 200


def test_datetime_range_validation():
    # Invalid datetime format
    res = client.get("/api/v1/system/hourly?start_time=invalid_dt")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "BAD_REQUEST"

    # Start time > end time
    res = client.get("/api/v1/system/hourly?start_time=2026-07-28T00:00:00&end_time=2026-07-20T00:00:00")
    assert res.status_code == 400

    # Valid ISO range
    res = client.get("/api/v1/system/hourly?start_time=2026-07-20T00:00:00&end_time=2026-07-27T23:59:59&limit=5")
    assert res.status_code == 200
    assert "data" in res.json()
