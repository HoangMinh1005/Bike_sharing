# REST API Endpoints Specification — Bike Sharing Operation Intelligence

This document details the read-only REST API endpoints exposed by the FastAPI serving application.

---

## 1. Base URL & Interactive Documentation

- **Local Base URL**: `http://localhost:8000`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`
- **ReDoc Documentation**: `http://localhost:8000/redoc`

---

## 2. Response Envelopes

All API endpoints follow a consistent JSON response envelope structure:

### Single Item Response:
```json
{
  "data": {
    "summary_date": "2026-07-31",
    "station_count": 2376,
    "active_station_count": 2371,
    "avg_availability_rate": 0.654
  }
}
```

### Paginated List Response:
```json
{
  "data": [
    {
      "station_id": "station_001",
      "station_name": "Broadway & W 25th St",
      "avg_bikes_available": 14.5
    }
  ],
  "meta": {
    "count": 1,
    "limit": 50,
    "offset": 0
  }
}
```

---

## 3. Endpoints Reference

### System Endpoints (`/api/v1/system`)

| Method | Endpoint | Query Parameters | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/health` | None | API service health check. |
| `GET` | `/api/v1/system/latest` | None | Get the latest daily system-wide summary metrics. |
| `GET` | `/api/v1/system/daily` | `start_date`, `end_date` | Get historical daily system summary metrics over date range. |
| `GET` | `/api/v1/system/hourly` | `limit`, `offset` | Get system-wide hourly weather and mobility summary metrics. |

### Stations Endpoints (`/api/v1/stations`)

| Method | Endpoint | Query Parameters | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/stations/daily` | `summary_date`, `limit`, `offset`, `sort_by` | Get daily station availability summary metrics for target date. |
| `GET` | `/api/v1/stations/search` | `q`, `limit` | Search stations by keyword in name or short_name. |
| `GET` | `/api/v1/stations/{station_id}/daily` | `start_date`, `end_date` | Get daily history for a specific station over date range. |
| `GET` | `/api/v1/stations/{station_id}/hourly` | `start_time`, `end_time`, `limit`, `offset` | Get hourly availability records for a specific station. |

### Regions Endpoints (`/api/v1/regions`)

| Method | Endpoint | Query Parameters | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/regions/daily` | `summary_date`, `limit`, `offset` | Get daily region summary metrics for target date. |
| `GET` | `/api/v1/regions/{region_id}/daily` | `start_date`, `end_date` | Get daily history for a specific region over date range. |
| `GET` | `/api/v1/regions/{region_id}/stations` | `summary_date`, `limit`, `offset` | List stations belonging to a specific region on target date. |

### Ranking Endpoints (`/api/v1/ranking`)

| Method | Endpoint | Query Parameters | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/ranking/stations` | `ranking_date`, `top_n`, `demand_category` | Get station demand rankings for a target date. |
| `GET` | `/api/v1/ranking/stations/top-demand` | `ranking_date`, `top_n` | Get top-N high demand stations for a target date. |
| `GET` | `/api/v1/ranking/stations/{station_id}` | `ranking_date` | Get demand rank and score for a specific station. |

### Pipeline Metadata Endpoints (`/api/v1/pipelines`)

| Method | Endpoint | Query Parameters | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/pipelines/health/latest` | None | Get latest SLA freshness & health summary across all monitored DAGs. |
| `GET` | `/api/v1/pipelines/health/status/{health_status}` | None | Get monitored pipelines filtered by health status (`HEALTHY`, `STALE`, `FAILED`). |
| `GET` | `/api/v1/pipelines/health/{dag_id}` | None | Get health summary for a specific monitored DAG. |
| `GET` | `/api/v1/pipelines/runs/latest` | `limit` | Get recent pipeline runs execution history from `etl_metadata.pipeline_runs`. |

### Data Freshness Endpoints (`/api/v1/freshness`)

| Method | Endpoint | Query Parameters | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/freshness/summary` | None | Get system-wide data currency metrics, ingestion lags, and DAG execution statuses. |

#### Freshness Latency Thresholds & Status Rules:

| Component | Healthy (Live) | Warning (Lagging) | Stale (Delayed) | Unknown |
| :--- | :--- | :--- | :--- | :--- |
| **Station Status Snapshot** | $\le 30$ minutes lag | $30 - 60$ minutes lag | $> 60$ minutes lag | No data / Table missing |
| **Hourly Mobility Mart** | $\le 2$ hours ($120$m) lag | $2 - 4$ hours ($120-240$m) lag | $> 4$ hours ($> 240$m) lag | No data / Table missing |
| **Daily Summary Mart** | Today or Yesterday ($\le 1$ day) | $2$ days ago | $> 2$ days ago | No data / Table missing |
| **Overall System Status** | Worst among all components: $\text{HEALTHY} < \text{WARNING} < \text{STALE} < \text{UNKNOWN}$ | | | |

#### Example Freshness Response:
```json
{
  "data": {
    "status": "HEALTHY",
    "checked_at": "2026-08-13T04:00:00Z",
    "latest_station_status_snapshot_at": "2026-08-13T03:50:00Z",
    "station_status_lag_minutes": 10.0,
    "latest_hourly_mart_at": "2026-08-13T03:00:00Z",
    "hourly_mart_lag_minutes": 60.0,
    "latest_daily_summary_date": "2026-08-12",
    "latest_pipeline_health_status": "HEALTHY",
    "latest_successful_dag_runs": [
      {
        "dag_id": "station_status_snapshot_dag",
        "latest_success_at": "2026-08-13T03:50:00Z",
        "lag_minutes": 10.0,
        "status": "HEALTHY"
      }
    ],
    "warnings": []
  }
}
```

---

## 4. Example cURL Commands

```bash
# Health check
curl -X GET "http://localhost:8000/api/v1/health"

# Get latest system summary
curl -X GET "http://localhost:8000/api/v1/system/latest"

# Get daily station availability sorted by availability rate
curl -X GET "http://localhost:8000/api/v1/stations/daily?summary_date=2026-07-31&limit=10&sort_by=avg_availability_rate"

# Search stations matching "Broadway"
curl -X GET "http://localhost:8000/api/v1/stations/search?q=Broadway&limit=5"

# Get top 10 high demand stations for ranking date
curl -X GET "http://localhost:8000/api/v1/ranking/stations/top-demand?ranking_date=2026-07-31&top_n=10"

# Get latest pipeline health status summary
curl -X GET "http://localhost:8000/api/v1/pipelines/health/latest"
```

---

## 5. Operational Notes

1. **Read-only**: All API endpoints are strict `GET` operations. They never mutate database state or trigger Airflow DAGs.
2. **Data Sources**: The API reads exclusively from optimized `mart` tables and `etl_metadata` tables (never from `raw` tables).
3. **Validation**: Date parameters enforce `YYYY-MM-DD` format. DateTime parameters enforce ISO format (`YYYY-MM-DDTHH:mm:ss`). Invalid input returns `400 Bad Request`.
4. **Sort Whitelist**: Endpoint sorting parameters validate column names against strict whitelists to eliminate SQL injection risk.
5. **Caching**: Endpoint responses use Redis caching when available. If Redis is unavailable, the API falls back directly to PostgreSQL queries without disruption.
