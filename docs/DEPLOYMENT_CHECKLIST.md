# Post-Deployment Verification Checklist

Use this checklist to verify the stability, security, and integrity of the **GBFS Bike Sharing Operation Intelligence** deployment on your Ubuntu VM/VPS.

---

## 1. Container & Infrastructure Health

| Item | Verification Command | Expected Result | Status |
| :--- | :--- | :--- | :---: |
| **PostgreSQL Container** | `docker compose -f docker-compose.prod.yml ps postgres` | State `Up (healthy)` | [ ] |
| **Redis Container** | `docker compose -f docker-compose.prod.yml ps redis` | State `Up (healthy)` | [ ] |
| **Airflow Webserver** | `docker compose -f docker-compose.prod.yml ps airflow-webserver` | State `Up (healthy)` | [ ] |
| **Airflow Scheduler** | `docker compose -f docker-compose.prod.yml ps airflow-scheduler` | State `Up (healthy)` | [ ] |
| **FastAPI Backend** | `docker compose -f docker-compose.prod.yml ps fastapi` | State `Up (healthy)` | [ ] |
| **React Frontend** | `docker compose -f docker-compose.prod.yml ps frontend` | State `Up` | [ ] |

---

## 2. API & Network Connectivity

| Checkpoint | Action / Command | Expected Output | Status |
| :--- | :--- | :--- | :---: |
| **FastAPI Health Endpoint** | `curl http://localhost:8000/api/v1/health` | `{"status":"healthy","database":"connected","cache":"connected"}` | [ ] |
| **System Overview API** | `curl http://localhost:8000/api/v1/system/latest` | Returns latest summary record with HTTP 200 | [ ] |
| **Pipeline Health API** | `curl http://localhost:8000/api/v1/pipelines/health` | Returns DAG health statuses with HTTP 200 | [ ] |
| **No Public PostgreSQL Port** | `curl -s --connect-timeout 2 http://<server-ip>:5432` | Connection refused / timed out | [ ] |
| **No Public Redis Port** | `curl -s --connect-timeout 2 http://<server-ip>:6379` | Connection refused / timed out | [ ] |

---

## 3. Frontend & User Experience

| Checkpoint | Test Method | Expected Behavior | Status |
| :--- | :--- | :--- | :---: |
| **Dashboard Loading** | Open `http://<server-ip>:3000` | Landing page renders immediately without console errors | [ ] |
| **API Data Integration** | Check KPI Cards & Charts | System availability, bike counts, and trends render real data | [ ] |
| **Client-Side Routing** | Navigate to `/stations`, `/regions`, `/ranking` | Pages load smoothly; F5 / refresh does not return 404 | [ ] |
| **Station Detail Navigation** | Click on a station in Stations page | Station Detail page loads with KPI and trend charts | [ ] |
| **Region Detail Navigation** | Click on a region in Regions page | Region Detail page loads with KPI and station table | [ ] |
| **Pipeline Health Page** | Open `/health` route | Shows real-time DAG health table and freshness metrics | [ ] |

---

## 4. Airflow Data Pipeline Execution

| DAG Identifier | Trigger Method | Expected Execution Result | Status |
| :--- | :--- | :--- | :---: |
| **`gbfs_metadata_daily_dag`** | Airflow UI / CLI trigger | Success; populates `raw.gbfs_station_information` & `staging.stg_stations` | [ ] |
| **`station_status_snapshot_dag`** | Airflow UI / CLI trigger | Success; populates `raw.gbfs_station_status` & `staging.stg_station_status_snapshots` | [ ] |
| **`weather_calendar_sync_dag`** | Airflow UI / CLI trigger | Success; populates `raw.weather_hourly_raw` & `raw.calendar_dim` | [ ] |
| **`hourly_mart_build_dag`** | Airflow UI / CLI trigger | Success; populates `mart.weather_mobility_summary` | [ ] |
| **`daily_summary_dag`** | Airflow UI / CLI trigger | Success; populates `mart.daily_system_summary`, `mart.daily_region_summary`, `mart.daily_station_summary` | [ ] |
| **`pipeline_health_dag`** | Airflow UI / CLI trigger | Success; updates `etl_metadata.pipeline_health_summary` | [ ] |

---

## 5. PostgreSQL Data Layer Validation

Execute in PostgreSQL (`docker compose -f docker-compose.prod.yml exec postgres psql -U postgres -d bike_sharing`):

```sql
-- 1. Staging Stations Count (> 0)
SELECT COUNT(*) AS total_stations FROM staging.stg_stations;

-- 2. Staging Status Snapshots Count (> 0)
SELECT COUNT(*) AS total_snapshots FROM staging.stg_station_status_snapshots;

-- 3. Daily System Summary (> 0)
SELECT COUNT(*) AS total_daily_summaries FROM mart.daily_system_summary;

-- 4. Hourly Weather Mobility Mart (> 0)
SELECT COUNT(*) AS total_hourly_records FROM mart.weather_mobility_summary;

-- 5. Pipeline Health Status Records (= 5)
SELECT dag_id, pipeline_status, freshness_status, volume_status 
FROM etl_metadata.pipeline_health_summary;
```

---

## 6. Persistence & Disaster Recovery

| Verification Step | Command / Procedure | Expected Result | Status |
| :--- | :--- | :--- | :---: |
| **Named Volumes Created** | `docker volume ls \| grep bike` | `bike_postgres_data`, `bike_redis_data`, `bike_airflow_logs` listed | [ ] |
| **PostgreSQL Backup Script** | `bash scripts/backup_postgres.sh` | Generates non-empty `.sql` dump in `backups/` directory | [ ] |
| **PostgreSQL Restore Script** | `bash scripts/restore_postgres.sh backups/<latest_file>.sql` | Restores database successfully without errors | [ ] |
| **Container Restart Resilience** | `docker compose -f docker-compose.prod.yml restart` | All services recover healthy state; no data loss | [ ] |
