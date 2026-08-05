# Operational Runbook — Bike Sharing Operation Intelligence

This document provides operational guidelines, DAG schedules, CLI commands, backfill/retention procedures, testing commands, and troubleshooting steps for the **Bike Sharing Operation Intelligence** platform.

---

## 1. Project Overview

**Bike Sharing Operation Intelligence** is an end-to-end data pipeline and analytics platform for real-time bike sharing mobility data (GBFS format), enriched with Open-Meteo weather data and holiday/calendar metadata.

### Core Objectives:
1. **Ingestion**: Raw JSON snapshot ingestion of GBFS metadata and status feeds.
2. **Staging & Enrichment**: Cleaning status data and enriching with hourly weather and holiday metadata.
3. **Data Marts**: Building business-grained hourly and daily data marts for station availability, region demand, vehicle types, and weather mobility correlation.
4. **Pipeline Health**: Automated data quality checks, SLA freshness monitoring, and pipeline tracking.
5. **REST API**: Read-only FastAPI service exposing analytical metrics for dashboards and downstream tools.

---

## 2. System Architecture & Components

| Component | Technology | Description |
| :--- | :--- | :--- |
| **External Sources** | GBFS, Open-Meteo API, Nager.Date | Raw feed snapshots, hourly weather metrics, calendar holidays. |
| **Orchestration** | Apache Airflow 2.10 | Scheduled ETL DAGs and manual operational tasks. |
| **Storage** | PostgreSQL 15 | Schemas: `raw`, `staging`, `mart`, `etl_metadata`. |
| **Serving API** | FastAPI + Uvicorn | Read-only endpoints with response schemas, pagination, and sort whitelists. |
| **Cache Layer** | Redis 7 (Optional) | Fast caching for API read endpoints with automatic fallback on failure. |
| **Metadata Tracking** | PostgreSQL `etl_metadata` | `pipeline_runs`, `watermarks`, `dq_results`, `rejected_records`, `pipeline_health_summary`. |

---

## 3. Airflow DAG Reference

| DAG ID | Schedule | Purpose | Source Tables | Target Tables |
| :--- | :--- | :--- | :--- | :--- |
| `gbfs_metadata_daily_dag` | `0 0 * * *` | Ingest GBFS metadata feeds | GBFS API | `raw.gbfs_feed_snapshots`, `staging.stations`, `staging.regions`, `staging.vehicle_types` |
| `station_status_snapshot_dag` | `*/15 * * * *` | Ingest station status snapshots | GBFS Status API | `raw.station_status_snapshots`, `staging.station_status`, `staging.station_vehicle_type_status` |
| `weather_calendar_sync_dag` | `0 */3 * * *` | Sync weather and calendar data | Open-Meteo, Nager.Date | `raw.weather_hourly`, `raw.calendar`, `staging.weather_hourly`, `staging.calendar` |
| `hourly_mart_build_dag` | `15 * * * *` | Build hourly availability marts | `staging.*` | `mart.hourly_station_availability`, `mart.hourly_region_availability`, `mart.vehicle_type_availability_summary`, `mart.weather_mobility_summary` |
| `daily_summary_dag` | `30 1 * * *` | Build daily summaries & rankings | `mart.hourly_*` | `mart.daily_station_summary`, `mart.daily_region_summary`, `mart.daily_system_summary`, `mart.station_demand_ranking` |
| `pipeline_health_dag` | `0 * * * *` | Check SLA freshness & DQ summary | `etl_metadata.*` | `etl_metadata.pipeline_health_summary` |
| `backfill_mart_dag` | `None` (Manual) | Rebuild historical mart data | `staging.*` | `mart.hourly_*`, `mart.daily_*` |
| `retention_cleanup_dag` | `30 3 * * *` | Purge expired historical logs | `raw.*`, `staging.*`, `etl_metadata.*` | Table retention purge |

---

## 4. Common CLI Commands

### Service Management (Docker Compose)
```bash
# Start all services in background
docker compose up -d --build

# Check status of containers
docker compose ps

# View logs for Airflow Scheduler
docker compose logs -f airflow-scheduler

# View logs for FastAPI service
docker compose logs -f fastapi

# Stop all services
docker compose down
```

### Operational Inspection & Testing
```bash
# Inspect database state and table row counts
docker compose exec fastapi python scripts/check_database_state.py

# Run unit tests (logic only, no DB required)
docker compose exec fastapi pytest tests/unit/

# Run integration tests (requires running PostgreSQL and FastAPI)
docker compose exec fastapi pytest tests/integration/

# Run API endpoint integration tests specifically
docker compose exec fastapi pytest tests/integration/test_fastapi_endpoints.py

# Run retention cleanup dry-run smoke test
docker compose exec fastapi pytest tests/integration/test_retention_cleanup.py
```

---

## 5. Backfill Operational Guide

`backfill_mart_dag` is triggered manually via Airflow UI or CLI with `dag_run.conf`.

### Configuration Examples:

#### 1. Hourly Backfill Only
Rebuilds hourly mart tables for window `[start, end)` (half-open: start inclusive, end exclusive).
```json
{
  "backfill_type": "hourly",
  "start": "2026-07-01T00:00:00",
  "end": "2026-07-01T06:00:00"
}
```

#### 2. Daily Backfill Only
Rebuilds daily mart tables for date range `[start_date, end_date]` (inclusive).
```json
{
  "backfill_type": "daily",
  "start": "2026-07-01",
  "end": "2026-07-07"
}
```

#### 3. Both Hourly and Daily Backfill
Rebuilds hourly mart windows over `[start, end)` first, then rebuilds affected daily dates.
```json
{
  "backfill_type": "both",
  "start": "2026-07-01T00:00:00",
  "end": "2026-07-08T00:00:00"
}
```

### Operational Limits:
- Hourly range limit: Max 31 days.
- Daily range limit: Max 366 days.

---

## 6. Data Retention Cleanup Guide

`retention_cleanup_dag` runs daily at `03:30 UTC` to clean historical logs based on `RETENTION_POLICIES`.

### Applied Retention Policies:
- `raw.gbfs_feed_snapshots`: 30 days (`fetched_at`)
- `raw.station_status_snapshots`: 45 days (`fetched_at`) — *45-day retention supports 31-day backfill window plus operational buffer.*
- `raw.weather_hourly`: 45 days (`fetched_at`)
- `raw.calendar`: 400 days (`loaded_at`)
- `staging.station_status`: 45 days (`fetched_at`)
- `staging.station_vehicle_type_status`: 45 days (`fetched_at`)
- `staging.weather_hourly`: 90 days (`fetched_at`)
- `staging.calendar`: 400 days (`updated_at`)
- `etl_metadata.dq_results`: 90 days (`checked_at`)
- `etl_metadata.rejected_records`: 90 days (`created_at`)
- `etl_metadata.pipeline_health_summary`: 90 days (`checked_at`)
- `etl_metadata.pipeline_runs`: 180 days (`started_at`)
- `mart.*` tables: **Disabled by default** to preserve dashboard history.

### Manual Dry-Run Execution:
To test retention cleanup without deleting any data:
```json
{
  "dry_run": true
}
```

---

## 7. Testing Strategy Guide

- **`tests/unit/`**: Pure Python unit tests testing config parsing, interval generators, and policy validations. No database connection required.
- **`tests/integration/`**: End-to-end integration tests validating PostgreSQL table state, FastAPI endpoints, small-range backfills, and retention dry-runs.
- **`scripts/check_database_state.py`**: CLI utility tool for fast database sanity inspection.

---

## 8. Troubleshooting Matrix

| Problem | Root Cause | Solution |
| :--- | :--- | :--- |
| Airflow DAG missing in UI | Syntax error or invalid import in DAG file | Run `docker compose exec airflow-scheduler python dags/<dag_name>.py` to inspect tracebacks. |
| Task fails with `ModuleNotFoundError: src` | Python import path missing workspace root | Ensure imports use `src.common...` or set `PYTHONPATH=/opt/airflow`. |
| Database connection failed (`OperationalError`) | Postgres service starting or wrong host | Verify `POSTGRES_HOST=postgres` in Docker environment and check container health with `docker compose ps`. |
| FastAPI returns 404 or empty data | Mart tables have not been populated yet | Run `hourly_mart_build_dag` and `daily_summary_dag` in Airflow. |
| Backfill returns 0 rows loaded | Staging source data missing for target range | Inspect `staging.station_status` timestamps using `python scripts/check_database_state.py`. |
| Retention policy error | Target table/column not in whitelist | Verify `table_name` and `timestamp_column` match `RETENTION_POLICIES` in `src/cleanup/retention_manager.py`. |
| Redis unavailable | Redis service down or network blocked | API automatically falls back to direct PostgreSQL query execution without crashing. |

---

## 9. Data Quality Checklist

1. **Raw Layer**: Snapshots present, non-null payloads, valid source timestamps.
2. **Staging Layer**: Valid station IDs, numeric metrics >= 0, no duplicate key violations.
3. **Hourly Mart**: `hourly_station_availability` non-empty, rates within [0, 1].
4. **Daily Mart**: Summaries non-empty, `demand_rank` > 0, `demand_score` >= 0.
5. **Pipeline Health**: `health_status` is `HEALTHY` or `WARNING` (no unexpected `STALE` or `FAILED`).
6. **API Layer**: `/health` returns HTTP 200, response matches envelope schemas.
