# Data Validation Checklist — Bike Sharing Operation Intelligence

This checklist defines standard verification criteria for inspecting data quality and operational readiness across all platform layers.

---

## 1. Raw Layer Checklist

- [ ] **Feed Snapshots**: `raw.gbfs_feed_snapshots` contains regular JSON snapshots for metadata feeds.
- [ ] **Status Snapshots**: `raw.station_status_snapshots` contains 15-minute status snapshots.
- [ ] **Weather Records**: `raw.weather_hourly` contains 3-hourly Open-Meteo hourly weather payloads.
- [ ] **Calendar Records**: `raw.calendar` contains valid holiday/date records.
- [ ] **Payload Integrity**: `raw_payload` or `raw_station_status` JSONB payloads are non-null and valid JSON.
- [ ] **Timestamp Validity**: `fetched_at` and `source_last_updated` timestamps are non-null and not in the future.

---

## 2. Staging Layer Checklist

- [ ] **Station Identifier**: `station_id` is non-null and non-empty across `staging.stations`, `staging.station_status`, and `staging.station_vehicle_type_status`.
- [ ] **Non-Negative Metrics**: `num_bikes_available`, `num_docks_available`, `num_bikes_disabled`, `num_docks_disabled` are >= 0.
- [ ] **Boolean Status Flags**: `is_installed`, `is_renting`, `is_returning` are non-null booleans.
- [ ] **Key Uniqueness**: No duplicate primary key records exist for `(station_id, batch_id)` in `staging.station_status`.
- [ ] **Enriched Staging Weather**: `temperature`, `humidity`, `precipitation`, `wind_speed` in `staging.weather_hourly` match reasonable physical bounds.

---

## 3. Hourly Mart Checklist

- [ ] **Station Hourly Availability**: `mart.hourly_station_availability` is non-empty for completed hourly buckets.
- [ ] **Region Hourly Availability**: `mart.hourly_region_availability` contains aggregated metrics grouped by `(hour_bucket, region_id)`.
- [ ] **Weather Mobility Summary**: `mart.weather_mobility_summary` contains 1 record per hour bucket enriched with weather metrics.
- [ ] **Observation Counts**: `observation_count` > 0 for all hourly station records.
- [ ] **Bounded Rates**: `availability_rate` and `dock_utilization_rate` strictly fall within `[0.0, 1.0]` range.
- [ ] **Uniqueness**: No duplicate `(hour_bucket, station_id)` or `(hour_bucket, region_id)` records exist.

---

## 4. Daily Mart Checklist

- [ ] **Daily Station Summary**: `mart.daily_station_summary` is non-empty for completed summary dates.
- [ ] **Daily Region Summary**: `mart.daily_region_summary` contains aggregated daily station metrics per region.
- [ ] **Daily System Summary**: `mart.daily_system_summary` contains exactly 1 row per `summary_date`.
- [ ] **Station Demand Ranking**: `mart.station_demand_ranking` contains demand ranks (`demand_rank` > 0) and scores (`demand_score` >= 0) matching station summary row count.
- [ ] **Valid Categories**: `demand_category` in `mart.station_demand_ranking` is strictly one of `'HIGH'`, `'MEDIUM'`, or `'LOW'`.

---

## 5. Pipeline Health & DQ Metadata Checklist

- [ ] **Pipeline Runs**: `etl_metadata.pipeline_runs` records recent DAG run executions with `status = 'success'`.
- [ ] **DQ Checks**: `etl_metadata.dq_results` contains `passed` status for all `CRITICAL` data quality checks.
- [ ] **Watermarks**: `etl_metadata.watermarks` contains up-to-date watermark values for all active pipelines.
- [ ] **SLA Freshness**: `freshness_lag_minutes` in `etl_metadata.pipeline_health_summary` does not exceed configured freshness thresholds.
- [ ] **Overall Health Status**: `health_status` in `etl_metadata.pipeline_health_summary` is `HEALTHY` or `WARNING` (no unexpected `FAILED` or `STALE` statuses).

---

## 6. API Layer Checklist

- [ ] **Health Check**: `GET /api/v1/health` returns HTTP 200 with status `'healthy'`.
- [ ] **Latest System Metrics**: `GET /api/v1/system/latest` returns HTTP 200 with valid `summary_date`.
- [ ] **Response Envelope**: All endpoints wrap payloads in standard `{ "data": ... }` or `{ "data": [...], "meta": ... }` envelopes.
- [ ] **Pagination Metadata**: Paginated endpoints return correct `limit`, `offset`, and `count` metadata.
- [ ] **Validation Enforcement**: Passing invalid date strings (e.g., `start_date=abc`) returns HTTP 400 Bad Request.
- [ ] **Sort Whitelist**: Passing unallowed `sort_by` fields returns HTTP 400 Bad Request.
