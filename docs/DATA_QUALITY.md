# Data Quality (DQ) Architecture & Station-Region Mapping Policy

This document details the Data Quality (DQ) monitoring design, severity hierarchy, and threshold policies implemented in the GBFS Bike Sharing Operation Intelligence platform.

---

## 1. Core Philosophy: Distinguishing Pipeline Failures from Source Data Limitations

In high-throughput operational intelligence platforms, **Warning Fatigue** occurs when known non-blocking source characteristics trigger constant `WARNING` or `ERROR` alerts, leading teams to overlook genuine pipeline outages.

### Primary vs. Secondary Operational Keys
* **`station_id` (Primary Operational Key)**:
  * Mandatory foreign key linking `staging.station_status` to `staging.stations`.
  * If a real-time observation references a station not found in metadata $\rightarrow$ **`CRITICAL` / `ERROR`** (Halts task, flags Pipeline Health as `FAILED`).
* **`region_id` (Secondary Categorization Attribute)**:
  * In the international **GBFS specification**, `region_id` in `station_information.json` is **optional**. Stations located outside administrative boroughs or boundary zones may legitimately omit `region_id`.
  * Missing or unmapped `region_id` is a **Known Non-Blocking Data Limitation**, not a pipeline execution failure.

---

## 2. Threshold-Based DQ Policy for Station-Region Mapping

Rather than failing or warning on any single missing `region_id`, the system monitors the **`missing_or_unmapped_region_rate`**:

$$\text{Rate} = \frac{\text{Station Count with Missing or Unmapped Region ID}}{\text{Total Station Count}}$$

| Missing Rate Range | DQ Severity | DQ Check Status | Impact on Pipeline Health | System Action |
| :--- | :---: | :---: | :---: | :--- |
| **$\le 1.0\%$** | **`INFO`** | `passed` | **`HEALTHY`** (No impact) | Station assigned to `UNKNOWN_REGION`. Logged as accepted limitation. |
| **$> 1.0\%$ and $\le 5.0\%$** | **`WARNING`** | `warning` | **`WARNING`** (Attention needed) | Logged with warning notice for operational inspection. |
| **$> 5.0\%$** | **`CRITICAL`** | `failed` | **`FAILED`** (Pipeline halted) | Triggers alert for potential upstream metadata schema corruption. |

---

## 3. UNKNOWN_REGION Handling Across the Data Stack

To guarantee **zero data loss** and prevent silent station omission from region-level analytical marts:

1. **Staging Layer (`staging.regions` & `staging.stations`)**:
   * `staging.regions` contains a standard seeded record: `region_id = 'UNKNOWN'`, `region_name = 'Unknown Region'`.
   * Unmapped or missing stations are explicitly assigned `region_id = 'UNKNOWN'`.
2. **Mart Layer (`mart.hourly_region_availability` & `mart.daily_region_summary`)**:
   * Stations with `region_id = 'UNKNOWN'` aggregate cleanly into `Unknown Region`.
   * `region_name` is guaranteed non-null via `COALESCE(region_name, 'Unknown Region')`.
3. **API & Dashboard**:
   * Dashboard renders `Unknown Region` as a normal grouping category without scary error alerts.
   * A dedicated **Data Quality Notes & Known Limitations** card explains the reason for unknown region assignments.

---

## 4. Summary of Data Quality Rules

| DQ Rule Name | Table | Checked Condition | Severity |
| :--- | :--- | :--- | :---: |
| `raw_station_status_snapshot_exists` | `raw.station_status_snapshots` | Batch snapshot table is not empty | `CRITICAL` |
| `raw_station_status_station_id_not_null` | `raw.station_status_snapshots` | `station_id` is NOT NULL / non-empty | `CRITICAL` |
| `staging_station_status_map_to_stations` | `staging.station_status` | Observation maps to `staging.stations` | `CRITICAL` |
| `stations_region_mapping` | `staging.stations` | Missing region rate ($\le 1\%$ / $1-5\%$ / $> 5\%$) | `INFO` / `WARN` / `CRIT` |
| `hourly_region_availability_not_empty` | `mart.hourly_region_availability` | Target hour region mart generated | `CRITICAL` |
| `daily_region_summary_not_empty` | `mart.daily_region_summary` | Target date region summary generated | `CRITICAL` |
