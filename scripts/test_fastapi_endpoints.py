import os
import sys
import httpx

from src.common.logger import get_logger

logger = get_logger(__name__)

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


def run_fastapi_smoke_tests():
    """
    Execute smoke test suite against FastAPI endpoints.
    """
    logger.info(f"Starting FastAPI endpoint smoke test. Target API_BASE_URL={API_BASE_URL}")

    # Use httpx.Client to make HTTP requests
    client = httpx.Client(base_url=API_BASE_URL, timeout=10.0)

    # 1. GET /api/v1/health
    logger.info("1. Testing GET /api/v1/health...")
    res = client.get("/api/v1/health")
    assert res.status_code == 200, f"Health check failed with status {res.status_code}: {res.text}"
    health_json = res.json()
    assert "data" in health_json, "Response missing 'data' key"
    assert health_json["data"]["status"] == "ok", f"API health status not ok: {health_json}"
    logger.info(f"   [PASSED] Health status: {health_json['data']}")

    # 2. GET /api/v1/system/latest
    logger.info("2. Testing GET /api/v1/system/latest...")
    res = client.get("/api/v1/system/latest")
    assert res.status_code == 200, f"System latest failed: {res.status_code}: {res.text}"
    system_latest = res.json()["data"]
    assert "summary_date" in system_latest, "System latest missing 'summary_date'"
    latest_date = str(system_latest["summary_date"])
    logger.info(f"   [PASSED] Latest system summary date: {latest_date}")

    # 3. GET /api/v1/pipelines/health/latest
    logger.info("3. Testing GET /api/v1/pipelines/health/latest...")
    res = client.get("/api/v1/pipelines/health/latest")
    assert res.status_code == 200, f"Pipeline health latest failed: {res.status_code}: {res.text}"
    pipeline_health = res.json()["data"]
    assert isinstance(pipeline_health, list), "Pipeline health response data must be a list"
    logger.info(f"   [PASSED] Evaluated {len(pipeline_health)} monitored pipeline health records.")

    # 4. GET /api/v1/stations/daily
    logger.info(f"4. Testing GET /api/v1/stations/daily?summary_date={latest_date}&limit=5...")
    res = client.get(f"/api/v1/stations/daily?summary_date={latest_date}&limit=5")
    assert res.status_code == 200, f"Stations daily failed: {res.status_code}: {res.text}"
    stations_json = res.json()
    assert "data" in stations_json and "meta" in stations_json
    logger.info(f"   [PASSED] Fetched {len(stations_json['data'])} station daily records.")

    # 5. GET /api/v1/regions/daily
    logger.info(f"5. Testing GET /api/v1/regions/daily?summary_date={latest_date}&limit=5...")
    res = client.get(f"/api/v1/regions/daily?summary_date={latest_date}&limit=5")
    assert res.status_code == 200, f"Regions daily failed: {res.status_code}: {res.text}"
    regions_json = res.json()
    assert "data" in regions_json and "meta" in regions_json
    logger.info(f"   [PASSED] Fetched {len(regions_json['data'])} region daily records.")

    # 6. GET /api/v1/ranking/stations
    logger.info(f"6. Testing GET /api/v1/ranking/stations?ranking_date={latest_date}&top_n=5...")
    res = client.get(f"/api/v1/ranking/stations?ranking_date={latest_date}&top_n=5")
    assert res.status_code == 200, f"Ranking stations failed: {res.status_code}: {res.text}"
    ranking_json = res.json()
    assert "data" in ranking_json
    logger.info(f"   [PASSED] Fetched top {len(ranking_json['data'])} ranked stations.")

    # 7. GET /api/v1/stations/{station_id}/daily
    if ranking_json["data"]:
        sample_station_id = ranking_json["data"][0]["station_id"]
        logger.info(f"7. Testing GET /api/v1/stations/{sample_station_id}/daily?start_date={latest_date}&end_date={latest_date}...")
        res = client.get(f"/api/v1/stations/{sample_station_id}/daily?start_date={latest_date}&end_date={latest_date}")
        assert res.status_code == 200, f"Station daily detail failed: {res.status_code}: {res.text}"
        station_detail = res.json()["data"]
        logger.info(f"   [PASSED] Station '{sample_station_id}' detail history fetched successfully ({len(station_detail)} records).")

    # 8. GET /api/v1/pipelines/runs/latest
    logger.info("8. Testing GET /api/v1/pipelines/runs/latest...")
    res = client.get("/api/v1/pipelines/runs/latest")
    assert res.status_code == 200, f"Pipeline runs latest failed: {res.status_code}: {res.text}"
    runs_json = res.json()
    assert "data" in runs_json
    logger.info(f"   [PASSED] Fetched {len(runs_json['data'])} pipeline runs.")

    logger.info("==========================================================")
    logger.info("All FastAPI read-only endpoint smoke tests PASSED!")
    logger.info("==========================================================")


if __name__ == "__main__":
    try:
        run_fastapi_smoke_tests()
    except Exception as e:
        logger.error(f"FastAPI smoke tests failed: {e}")
        sys.exit(1)
