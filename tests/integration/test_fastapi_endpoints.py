import os
import requests
import pytest

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = 10.0


def assert_status_ok(response: requests.Response, expected_code: int = 200) -> None:
    """Helper to assert HTTP status code and output response on failure."""
    assert (
        response.status_code == expected_code
    ), f"Expected status {expected_code}, got {response.status_code}. Response body: {response.text}"


def assert_response_has_data(response_json: dict) -> None:
    """Helper to assert response JSON contains 'data' envelope key."""
    assert "data" in response_json, f"Response missing 'data' key: {response_json}"


def test_api_health_endpoint():
    """1. GET /api/v1/health"""
    url = f"{BASE_URL}/api/v1/health"
    resp = requests.get(url, timeout=TIMEOUT)
    assert_status_ok(resp, 200)
    data = resp.json()
    assert_response_has_data(data)


def test_system_latest_endpoint():
    """2. GET /api/v1/system/latest"""
    url = f"{BASE_URL}/api/v1/system/latest"
    resp = requests.get(url, timeout=TIMEOUT)
    assert_status_ok(resp, 200)
    data = resp.json()
    assert_response_has_data(data)
    assert "summary_date" in data["data"], "System latest response missing 'summary_date'"


def test_system_daily_endpoint():
    """3. GET /api/v1/system/daily"""
    latest_resp = requests.get(f"{BASE_URL}/api/v1/system/latest", timeout=TIMEOUT)
    assert_status_ok(latest_resp, 200)
    latest_date = latest_resp.json()["data"]["summary_date"]

    url = f"{BASE_URL}/api/v1/system/daily"
    params = {"start_date": latest_date, "end_date": latest_date}
    resp = requests.get(url, params=params, timeout=TIMEOUT)
    assert_status_ok(resp, 200)
    data = resp.json()
    assert_response_has_data(data)
    assert len(data["data"]) > 0, f"No daily system summary data for {latest_date}"


def test_system_hourly_endpoint():
    """4. GET /api/v1/system/hourly"""
    url = f"{BASE_URL}/api/v1/system/hourly"
    params = {"limit": 5, "offset": 0}
    resp = requests.get(url, params=params, timeout=TIMEOUT)
    assert_status_ok(resp, 200)
    data = resp.json()
    assert_response_has_data(data)


def test_stations_daily_endpoint():
    """5. GET /api/v1/stations/daily"""
    latest_resp = requests.get(f"{BASE_URL}/api/v1/system/latest", timeout=TIMEOUT)
    assert_status_ok(latest_resp, 200)
    latest_date = latest_resp.json()["data"]["summary_date"]

    url = f"{BASE_URL}/api/v1/stations/daily"
    params = {"summary_date": latest_date, "limit": 5, "offset": 0}
    resp = requests.get(url, params=params, timeout=TIMEOUT)
    assert_status_ok(resp, 200)
    data = resp.json()
    assert_response_has_data(data)
    assert "meta" in data, "Paginated stations daily missing 'meta'"
    assert data["meta"]["limit"] == 5, f"Expected limit 5 in meta, got {data['meta']['limit']}"


def test_stations_search_endpoint():
    """6. GET /api/v1/stations/search"""
    latest_resp = requests.get(f"{BASE_URL}/api/v1/system/latest", timeout=TIMEOUT)
    latest_date = latest_resp.json()["data"]["summary_date"]

    # Get sample station_name
    st_resp = requests.get(f"{BASE_URL}/api/v1/stations/daily", params={"summary_date": latest_date, "limit": 1}, timeout=TIMEOUT)
    assert_status_ok(st_resp, 200)
    stations_list = st_resp.json()["data"]
    assert len(stations_list) > 0, "No stations returned from stations daily."

    sample_name = stations_list[0].get("station_name", "Station")
    query_term = sample_name[:3] if sample_name else "St"

    url = f"{BASE_URL}/api/v1/stations/search"
    resp = requests.get(url, params={"q": query_term, "limit": 5}, timeout=TIMEOUT)
    assert_status_ok(resp, 200)
    data = resp.json()
    assert_response_has_data(data)


def test_station_daily_history_endpoint():
    """7. GET /api/v1/stations/{station_id}/daily"""
    latest_resp = requests.get(f"{BASE_URL}/api/v1/system/latest", timeout=TIMEOUT)
    latest_date = latest_resp.json()["data"]["summary_date"]

    st_resp = requests.get(f"{BASE_URL}/api/v1/stations/daily", params={"summary_date": latest_date, "limit": 1}, timeout=TIMEOUT)
    station_id = st_resp.json()["data"][0]["station_id"]

    url = f"{BASE_URL}/api/v1/stations/{station_id}/daily"
    params = {"start_date": latest_date, "end_date": latest_date}
    resp = requests.get(url, params=params, timeout=TIMEOUT)
    assert_status_ok(resp, 200)
    data = resp.json()
    assert_response_has_data(data)


def test_regions_daily_endpoint():
    """8. GET /api/v1/regions/daily"""
    latest_resp = requests.get(f"{BASE_URL}/api/v1/system/latest", timeout=TIMEOUT)
    latest_date = latest_resp.json()["data"]["summary_date"]

    url = f"{BASE_URL}/api/v1/regions/daily"
    params = {"summary_date": latest_date, "limit": 5, "offset": 0}
    resp = requests.get(url, params=params, timeout=TIMEOUT)
    assert_status_ok(resp, 200)
    data = resp.json()
    assert_response_has_data(data)


def test_region_daily_history_endpoint():
    """9. GET /api/v1/regions/{region_id}/daily"""
    latest_resp = requests.get(f"{BASE_URL}/api/v1/system/latest", timeout=TIMEOUT)
    latest_date = latest_resp.json()["data"]["summary_date"]

    reg_resp = requests.get(f"{BASE_URL}/api/v1/regions/daily", params={"summary_date": latest_date, "limit": 1}, timeout=TIMEOUT)
    assert_status_ok(reg_resp, 200)
    regions_list = reg_resp.json()["data"]

    if len(regions_list) > 0 and regions_list[0].get("region_id"):
        region_id = regions_list[0]["region_id"]
        url = f"{BASE_URL}/api/v1/regions/{region_id}/daily"
        params = {"start_date": latest_date, "end_date": latest_date}
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        assert_status_ok(resp, 200)
        assert_response_has_data(resp.json())


def test_ranking_stations_endpoint():
    """10. GET /api/v1/ranking/stations"""
    latest_resp = requests.get(f"{BASE_URL}/api/v1/system/latest", timeout=TIMEOUT)
    latest_date = latest_resp.json()["data"]["summary_date"]

    url = f"{BASE_URL}/api/v1/ranking/stations"
    params = {"ranking_date": latest_date, "top_n": 5}
    resp = requests.get(url, params=params, timeout=TIMEOUT)
    assert_status_ok(resp, 200)
    data = resp.json()
    assert_response_has_data(data)


def test_top_demand_ranking_endpoint():
    """11. GET /api/v1/ranking/stations/top-demand"""
    latest_resp = requests.get(f"{BASE_URL}/api/v1/system/latest", timeout=TIMEOUT)
    latest_date = latest_resp.json()["data"]["summary_date"]

    url = f"{BASE_URL}/api/v1/ranking/stations/top-demand"
    params = {"ranking_date": latest_date, "top_n": 5}
    resp = requests.get(url, params=params, timeout=TIMEOUT)
    assert_status_ok(resp, 200)
    data = resp.json()
    assert_response_has_data(data)


def test_pipelines_health_latest_endpoint():
    """12. GET /api/v1/pipelines/health/latest"""
    url = f"{BASE_URL}/api/v1/pipelines/health/latest"
    resp = requests.get(url, timeout=TIMEOUT)
    assert_status_ok(resp, 200)
    data = resp.json()
    assert_response_has_data(data)


def test_pipelines_runs_latest_endpoint():
    """13. GET /api/v1/pipelines/runs/latest"""
    url = f"{BASE_URL}/api/v1/pipelines/runs/latest"
    resp = requests.get(url, timeout=TIMEOUT)
    assert_status_ok(resp, 200)
    data = resp.json()
    assert_response_has_data(data)


def test_invalid_date_validation():
    """Test 400 Bad Request on invalid date string."""
    url = f"{BASE_URL}/api/v1/system/daily"
    params = {"start_date": "abc", "end_date": "abc"}
    resp = requests.get(url, params=params, timeout=TIMEOUT)
    assert_status_ok(resp, 400)


def test_sort_whitelist_validation():
    """Test sort whitelist validation (HTTP 200 on allowed sort, 400 on invalid sort)."""
    latest_resp = requests.get(f"{BASE_URL}/api/v1/system/latest", timeout=TIMEOUT)
    latest_date = latest_resp.json()["data"]["summary_date"]

    url = f"{BASE_URL}/api/v1/stations/daily"

    # Valid sort_by
    resp_valid = requests.get(url, params={"summary_date": latest_date, "sort_by": "avg_availability_rate"}, timeout=TIMEOUT)
    assert_status_ok(resp_valid, 200)

    # Invalid sort_by (sql injection / unallowed field)
    resp_invalid = requests.get(url, params={"summary_date": latest_date, "sort_by": "invalid_column;DROP"}, timeout=TIMEOUT)
    assert_status_ok(resp_invalid, 400)

    print("\nFASTAPI ENDPOINT SMOKE TEST PASSED")
