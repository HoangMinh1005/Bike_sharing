import pendulum
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.common.db import fetch_all, fetch_one
from src.common.logger import get_logger

logger = get_logger(__name__)

STATUS_ORDER = {
    "HEALTHY": 1,
    "WARNING": 2,
    "STALE": 3,
    "UNKNOWN": 4,
}

# Freshness Thresholds (in minutes)
STATION_STATUS_HEALTHY_MAX_MINUTES = 30.0
STATION_STATUS_WARNING_MAX_MINUTES = 60.0

HOURLY_MART_HEALTHY_MAX_MINUTES = 90.0   # 1.5 hours (max normal lag cycle is 80m before :20 run)
HOURLY_MART_WARNING_MAX_MINUTES = 180.0  # 3.0 hours

DAILY_SUMMARY_HEALTHY_MAX_DAYS = 1  # Today or yesterday
DAILY_SUMMARY_WARNING_MAX_DAYS = 2  # 2 days ago


def evaluate_station_status_freshness(lag_minutes: Optional[float]) -> str:
    """Evaluate freshness status for real-time station status snapshots."""
    if lag_minutes is None or lag_minutes < 0:
        return "UNKNOWN"
    if lag_minutes <= STATION_STATUS_HEALTHY_MAX_MINUTES:
        return "HEALTHY"
    if lag_minutes <= STATION_STATUS_WARNING_MAX_MINUTES:
        return "WARNING"
    return "STALE"


def evaluate_hourly_mart_freshness(lag_minutes: Optional[float]) -> str:
    """Evaluate freshness status for hourly data marts."""
    if lag_minutes is None or lag_minutes < 0:
        return "UNKNOWN"
    if lag_minutes <= HOURLY_MART_HEALTHY_MAX_MINUTES:
        return "HEALTHY"
    if lag_minutes <= HOURLY_MART_WARNING_MAX_MINUTES:
        return "WARNING"
    return "STALE"


def evaluate_daily_summary_freshness(latest_summary_date: Optional[date], current_date: date) -> str:
    """Evaluate freshness status for daily aggregated summaries."""
    if latest_summary_date is None:
        return "UNKNOWN"
    delta_days = (current_date - latest_summary_date).days
    if delta_days <= DAILY_SUMMARY_HEALTHY_MAX_DAYS:
        return "HEALTHY"
    if delta_days <= DAILY_SUMMARY_WARNING_MAX_DAYS:
        return "WARNING"
    return "STALE"


def evaluate_dag_run_freshness(dag_id: str, lag_minutes: Optional[float]) -> str:
    """Evaluate freshness status for individual Airflow DAG execution runs."""
    if lag_minutes is None or lag_minutes < 0:
        return "UNKNOWN"

    # Schedule-specific thresholds for DAG runs
    if dag_id == "station_status_snapshot_dag":
        return evaluate_station_status_freshness(lag_minutes)
    elif dag_id == "hourly_mart_build_dag":
        return evaluate_hourly_mart_freshness(lag_minutes)
    elif dag_id == "weather_calendar_sync_dag":
        if lag_minutes <= 180:  # 3 hours schedule
            return "HEALTHY"
        elif lag_minutes <= 360:
            return "WARNING"
        return "STALE"
    elif dag_id in ("daily_summary_dag", "gbfs_metadata_daily_dag", "pipeline_health_dag"):
        if lag_minutes <= 1440 + 360:  # Daily schedule (up to 30h)
            return "HEALTHY"
        elif lag_minutes <= 2880:  # 48h
            return "WARNING"
        return "STALE"

    # Generic fallback
    if lag_minutes <= 60:
        return "HEALTHY"
    elif lag_minutes <= 180:
        return "WARNING"
    return "STALE"


def calculate_overall_status(statuses: List[str]) -> str:
    """
    Determine overall freshness status based on worst component status.
    Hierarchy: HEALTHY < WARNING < STALE < UNKNOWN
    """
    if not statuses:
        return "UNKNOWN"
    worst_score = max(STATUS_ORDER.get(s.upper(), 4) for s in statuses)
    for status_str, score in STATUS_ORDER.items():
        if score == worst_score:
            return status_str
    return "UNKNOWN"


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure a datetime object has explicit UTC tzinfo."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _safe_fetch_watermarks() -> Dict[str, Dict[str, Any]]:
    """
    Fetch all pipeline watermarks from etl_metadata.watermarks in a single O(1) query.
    Returns a dictionary mapping source_name to row dict containing
    'last_successful_value' and 'updated_at'.
    """
    try:
        rows = fetch_all(
            """
            SELECT source_name, last_successful_value, updated_at
            FROM etl_metadata.watermarks
            """
        )
        return {r["source_name"]: r for r in rows if r.get("source_name")}
    except Exception as e:
        logger.debug(f"Query on etl_metadata.watermarks failed: {e}")
        return {}


def _safe_fetch_station_status_timestamp() -> Tuple[Optional[datetime], Optional[str]]:
    """
    Fetch the latest station status snapshot timestamp.
    Checks staging.station_status first, then raw.station_status_snapshots.
    Uses simple ORDER BY fetched_at DESC LIMIT 1 to match single-column B-tree indexes.
    """
    # 1. Try staging.station_status
    try:
        row = fetch_one(
            """
            SELECT source_last_updated, fetched_at
            FROM staging.station_status
            ORDER BY fetched_at DESC
            LIMIT 1
            """
        )
        if row:
            latest_ts = row.get("source_last_updated") or row.get("fetched_at")
            if latest_ts:
                return _ensure_utc(latest_ts), None
    except Exception as e:
        logger.debug(f"Query on staging.station_status failed: {e}")

    # 2. Try raw.station_status_snapshots
    try:
        row = fetch_one(
            """
            SELECT source_last_updated, fetched_at
            FROM raw.station_status_snapshots
            ORDER BY fetched_at DESC
            LIMIT 1
            """
        )
        if row:
            latest_ts = row.get("source_last_updated") or row.get("fetched_at")
            if latest_ts:
                return _ensure_utc(latest_ts), None
    except Exception as e:
        logger.debug(f"Query on raw.station_status_snapshots failed: {e}")

    return None, "No station status snapshot data found in staging or raw layer."


def _safe_fetch_hourly_mart_timestamp() -> Tuple[Optional[datetime], Optional[str]]:
    """
    Fetch the latest hourly mart timestamp using O(1) B-tree index lookup.
    """
    # 1. Try mart.hourly_station_availability
    try:
        row = fetch_one(
            """
            SELECT hour_bucket AS latest_ts 
            FROM mart.hourly_station_availability 
            ORDER BY hour_bucket DESC 
            LIMIT 1
            """
        )
        if row and row.get("latest_ts"):
            return _ensure_utc(row["latest_ts"]), None
    except Exception as e:
        logger.debug(f"Query on mart.hourly_station_availability failed: {e}")

    # 2. Try mart.weather_mobility_summary
    try:
        row = fetch_one(
            """
            SELECT hour_bucket AS latest_ts 
            FROM mart.weather_mobility_summary 
            ORDER BY hour_bucket DESC 
            LIMIT 1
            """
        )
        if row and row.get("latest_ts"):
            return _ensure_utc(row["latest_ts"]), None
    except Exception as e:
        logger.debug(f"Query on mart.weather_mobility_summary failed: {e}")

    return None, "No hourly mobility mart data found in mart schema."


def _safe_fetch_daily_summary_date() -> Tuple[Optional[date], Optional[str]]:
    """
    Fetch the latest daily summary date from mart.daily_system_summary using O(1) index lookup.
    """
    try:
        row = fetch_one(
            """
            SELECT summary_date AS latest_date 
            FROM mart.daily_system_summary 
            ORDER BY summary_date DESC 
            LIMIT 1
            """
        )
        if row and row.get("latest_date"):
            return row["latest_date"], None
    except Exception as e:
        logger.debug(f"Query on mart.daily_system_summary failed: {e}")

    return None, "No daily system summary data found in mart.daily_system_summary."


def _safe_fetch_latest_pipeline_health() -> Tuple[Optional[str], Optional[str]]:
    """
    Fetch the latest pipeline health summary status using O(1) index scan.
    """
    try:
        rows = fetch_all(
            """
            SELECT health_status
            FROM etl_metadata.pipeline_health_summary
            WHERE health_run_id = (
                SELECT health_run_id
                FROM etl_metadata.pipeline_health_summary
                ORDER BY checked_at DESC
                LIMIT 1
            )
            """
        )
        if rows:
            statuses = [r["health_status"] for r in rows if r.get("health_status")]
            if any(s == "FAILED" for s in statuses):
                return "FAILED", None
            if any(s == "STALE" for s in statuses):
                return "STALE", None
            if any(s == "WARNING" for s in statuses):
                return "WARNING", None
            return "HEALTHY", None
    except Exception as e:
        logger.debug(f"Query on etl_metadata.pipeline_health_summary failed: {e}")

    return None, "No pipeline health summary records found in etl_metadata."


def _safe_fetch_latest_successful_dag_runs(now_utc: datetime) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Fetch latest successful DAG execution runs using DISTINCT ON O(N_dags) fast scan.
    """
    known_dags = [
        "gbfs_metadata_daily_dag",
        "station_status_snapshot_dag",
        "weather_calendar_sync_dag",
        "hourly_mart_build_dag",
        "daily_summary_dag",
        "pipeline_health_dag",
    ]

    dag_runs_map: Dict[str, datetime] = {}

    # 1. Try etl_metadata.pipeline_runs
    try:
        rows = fetch_all(
            """
            SELECT DISTINCT ON (dag_id) dag_id, ended_at, started_at
            FROM etl_metadata.pipeline_runs
            WHERE UPPER(status) = 'SUCCESS'
            ORDER BY dag_id, started_at DESC
            """
        )
        for r in rows:
            latest_success_at = r.get("ended_at") or r.get("started_at")
            if r.get("dag_id") and latest_success_at:
                dag_runs_map[r["dag_id"]] = _ensure_utc(latest_success_at)
    except Exception as e:
        logger.debug(f"Query on etl_metadata.pipeline_runs failed: {e}")

    # 2. Fallback to etl_metadata.pipeline_health_summary if empty
    if not dag_runs_map:
        try:
            rows = fetch_all(
                """
                SELECT monitored_dag_id AS dag_id, latest_success_finished_at
                FROM etl_metadata.pipeline_health_summary
                WHERE health_run_id = (
                    SELECT health_run_id
                    FROM etl_metadata.pipeline_health_summary
                    ORDER BY checked_at DESC
                    LIMIT 1
                )
                """
            )
            for r in rows:
                if r.get("dag_id") and r.get("latest_success_finished_at"):
                    dag_runs_map[r["dag_id"]] = _ensure_utc(r["latest_success_finished_at"])
        except Exception as e:
            logger.debug(f"Fallback query on pipeline_health_summary failed: {e}")

    result = []
    for dag_id in known_dags:
        success_ts = dag_runs_map.get(dag_id)
        if success_ts:
            if isinstance(success_ts, str):
                try:
                    success_dt = pendulum.parse(success_ts)
                except Exception:
                    success_dt = now_utc
            else:
                success_dt = success_ts

            # Calculate lag
            if hasattr(success_dt, "tzinfo") and success_dt.tzinfo is not None:
                lag_min = max(0.0, (now_utc - success_dt).total_seconds() / 60.0)
            else:
                lag_min = max(0.0, (now_utc.replace(tzinfo=None) - success_dt).total_seconds() / 60.0)

            status = evaluate_dag_run_freshness(dag_id, lag_min)
            result.append(
                {
                    "dag_id": dag_id,
                    "latest_success_at": success_ts,
                    "lag_minutes": round(lag_min, 1),
                    "status": status,
                }
            )
        else:
            result.append(
                {
                    "dag_id": dag_id,
                    "latest_success_at": None,
                    "lag_minutes": None,
                    "status": "UNKNOWN",
                }
            )

    warning = None if dag_runs_map else "No completed DAG execution runs found in etl_metadata.pipeline_runs."
    return result, warning


import time

_FRESHNESS_CACHE: Optional[Dict[str, Any]] = None
_FRESHNESS_CACHE_TIME: float = 0.0
_CACHE_TTL_SECONDS: float = 15.0


def get_data_freshness_summary() -> Dict[str, Any]:
    """
    Compute comprehensive data freshness summary across all system components.
    Guarantees no unhandled exceptions even if tables are empty or missing.
    Uses multi-tier caching:
      1. Redis shared cache across workers (TTL=15s)
      2. In-memory per-process TTL cache fallback (TTL=15s)
    """
    global _FRESHNESS_CACHE, _FRESHNESS_CACHE_TIME

    # Tier 1: Try Redis shared cache across all Uvicorn workers
    try:
        from api.cache import get_cache
        cached = get_cache("bike_api:freshness_summary")
        if cached:
            return cached
    except Exception as e:
        logger.debug(f"Redis cache check failed: {e}")

    # Tier 2: In-memory fallback per-process
    now_mono = time.monotonic()
    if _FRESHNESS_CACHE is not None and (now_mono - _FRESHNESS_CACHE_TIME) < _CACHE_TTL_SECONDS:
        return _FRESHNESS_CACHE

    now_utc = pendulum.now("UTC")
    warnings: List[str] = []
    component_statuses: List[str] = []

    t_start = time.perf_counter()

    # 0. Single fast query to load all pipeline watermarks (< 1ms)
    t0 = time.perf_counter()
    watermarks = _safe_fetch_watermarks()
    t_watermarks = time.perf_counter() - t0

    # 1. Station Status Snapshot Freshness (from watermark: gbfs_station_status)
    t0 = time.perf_counter()
    snapshot_ts: Optional[datetime] = None
    snapshot_warn: Optional[str] = None
    wm_station = watermarks.get("gbfs_station_status")
    if wm_station and wm_station.get("last_successful_value"):
        try:
            snapshot_ts = _ensure_utc(pendulum.parse(wm_station["last_successful_value"]))
        except Exception as e:
            logger.debug(f"Failed to parse gbfs_station_status watermark: {e}")
            snapshot_ts = _ensure_utc(wm_station.get("updated_at"))
    elif wm_station and wm_station.get("updated_at"):
        snapshot_ts = _ensure_utc(wm_station["updated_at"])

    # Fallback to direct staging/raw table lookup if watermark missing
    if snapshot_ts is None:
        snapshot_ts, snapshot_warn = _safe_fetch_station_status_timestamp()
        if snapshot_warn:
            warnings.append(snapshot_warn)

    t_station_status = time.perf_counter() - t0

    snapshot_lag_min: Optional[float] = None
    if snapshot_ts:
        if hasattr(snapshot_ts, "tzinfo") and snapshot_ts.tzinfo is not None:
            snapshot_lag_min = max(0.0, (now_utc - snapshot_ts).total_seconds() / 60.0)
        else:
            snapshot_lag_min = max(0.0, (now_utc.replace(tzinfo=None) - snapshot_ts).total_seconds() / 60.0)
        snapshot_status = evaluate_station_status_freshness(snapshot_lag_min)
    else:
        snapshot_status = "UNKNOWN"
    component_statuses.append(snapshot_status)

    # 2. Hourly Mart Freshness (from watermark: hourly_mart)
    t0 = time.perf_counter()
    hourly_ts: Optional[datetime] = None
    hourly_warn: Optional[str] = None
    hourly_coverage_end: Optional[datetime] = None

    wm_hourly = watermarks.get("hourly_mart")
    if wm_hourly and wm_hourly.get("last_successful_value"):
        try:
            from datetime import timedelta
            # last_successful_value is target_hour_end (e.g. 2026-09-04 09:00:00)
            parsed_end = _ensure_utc(pendulum.parse(wm_hourly["last_successful_value"]))
            hourly_coverage_end = parsed_end
            # latest_hourly_mart_at represents the bucket start hour
            hourly_ts = parsed_end - timedelta(hours=1)
        except Exception as e:
            logger.debug(f"Failed to parse hourly_mart watermark: {e}")

    # Fallback to direct mart table lookup if watermark missing
    if hourly_ts is None:
        hourly_ts, hourly_warn = _safe_fetch_hourly_mart_timestamp()
        if hourly_warn:
            warnings.append(hourly_warn)
        if hourly_ts:
            from datetime import timedelta
            hourly_coverage_end = hourly_ts + timedelta(hours=1)

    t_hourly_mart = time.perf_counter() - t0

    hourly_lag_min: Optional[float] = None
    if hourly_coverage_end:
        if hasattr(hourly_coverage_end, "tzinfo") and hourly_coverage_end.tzinfo is not None:
            hourly_lag_min = max(0.0, (now_utc - hourly_coverage_end).total_seconds() / 60.0)
        else:
            hourly_lag_min = max(0.0, (now_utc.replace(tzinfo=None) - hourly_coverage_end).total_seconds() / 60.0)
        hourly_status = evaluate_hourly_mart_freshness(hourly_lag_min)
    else:
        hourly_status = "UNKNOWN"
    component_statuses.append(hourly_status)

    # 3. Daily Summary Freshness (from watermark: daily_summary)
    t0 = time.perf_counter()
    daily_date: Optional[date] = None
    daily_warn: Optional[str] = None

    wm_daily = watermarks.get("daily_summary")
    if wm_daily and wm_daily.get("last_successful_value"):
        try:
            daily_date = pendulum.parse(wm_daily["last_successful_value"]).date()
        except Exception as e:
            logger.debug(f"Failed to parse daily_summary watermark: {e}")

    # Fallback to direct mart table lookup if watermark missing
    if daily_date is None:
        daily_date, daily_warn = _safe_fetch_daily_summary_date()
        if daily_warn:
            warnings.append(daily_warn)

    t_daily_summary = time.perf_counter() - t0
    daily_status = evaluate_daily_summary_freshness(daily_date, now_utc.date())
    component_statuses.append(daily_status)

    # 4. Pipeline Health Status (Data Quality & Execution Integrity)
    t0 = time.perf_counter()
    health_status, health_warn = _safe_fetch_latest_pipeline_health()
    t_pipeline_health = time.perf_counter() - t0
    if health_warn:
        warnings.append(health_warn)
    quality_status = health_status or "UNKNOWN"

    # 5. Successful DAG Runs List (from watermarks updated_at)
    t0 = time.perf_counter()
    known_dags = [
        "gbfs_metadata_daily_dag",
        "station_status_snapshot_dag",
        "weather_calendar_sync_dag",
        "hourly_mart_build_dag",
        "daily_summary_dag",
        "pipeline_health_dag",
    ]
    dag_watermark_map = {
        "gbfs_metadata_daily_dag": "gbfs_metadata",
        "station_status_snapshot_dag": "gbfs_station_status",
        "weather_calendar_sync_dag": "weather_hourly",
        "hourly_mart_build_dag": "hourly_mart",
        "daily_summary_dag": "daily_summary",
        "pipeline_health_dag": "pipeline_health",
    }

    dag_runs: List[Dict[str, Any]] = []
    dag_warn: Optional[str] = None

    has_wm_dag_data = any(dag_watermark_map.get(d) in watermarks for d in known_dags)
    if has_wm_dag_data:
        for dag_id in known_dags:
            wm_source = dag_watermark_map.get(dag_id)
            wm_row = watermarks.get(wm_source) if wm_source else None
            success_ts = None
            if wm_row:
                success_ts = _ensure_utc(wm_row.get("updated_at"))
                if not success_ts and wm_row.get("last_successful_value"):
                    try:
                        success_ts = _ensure_utc(pendulum.parse(wm_row["last_successful_value"]))
                    except Exception:
                        pass

            if success_ts:
                if hasattr(success_ts, "tzinfo") and success_ts.tzinfo is not None:
                    lag_min = max(0.0, (now_utc - success_ts).total_seconds() / 60.0)
                else:
                    lag_min = max(0.0, (now_utc.replace(tzinfo=None) - success_ts).total_seconds() / 60.0)
                status = evaluate_dag_run_freshness(dag_id, lag_min)
                dag_runs.append({
                    "dag_id": dag_id,
                    "latest_success_at": success_ts,
                    "lag_minutes": round(lag_min, 1),
                    "status": status,
                })
            else:
                dag_runs.append({
                    "dag_id": dag_id,
                    "latest_success_at": None,
                    "lag_minutes": None,
                    "status": "UNKNOWN",
                })
    else:
        # Fallback to pipeline_runs table scan
        dag_runs, dag_warn = _safe_fetch_latest_successful_dag_runs(now_utc)
        if dag_warn:
            warnings.append(dag_warn)

    t_dag_runs = time.perf_counter() - t0
    t_total = time.perf_counter() - t_start

    print(
        f"[TIMING] freshness.watermarks = {t_watermarks:.6f}s\n"
        f"[TIMING] freshness.station_status = {t_station_status:.6f}s\n"
        f"[TIMING] freshness.hourly_mart = {t_hourly_mart:.6f}s\n"
        f"[TIMING] freshness.daily_summary = {t_daily_summary:.6f}s\n"
        f"[TIMING] freshness.pipeline_health = {t_pipeline_health:.6f}s\n"
        f"[TIMING] freshness.dag_runs = {t_dag_runs:.6f}s\n"
        f"[TIMING] freshness.total = {t_total:.6f}s",
        flush=True,
    )

    # Calculate overall time freshness status (excluding DQ warnings)
    time_statuses = list(component_statuses)
    for r in dag_runs:
        if r.get("status"):
            time_statuses.append(r["status"])

    overall_freshness_status = calculate_overall_status(time_statuses)

    # If data is fresh in time but pipeline health has non-critical quality warnings, add notice
    if overall_freshness_status == "HEALTHY" and quality_status == "WARNING":
        warnings.append("Data is Live and up-to-date; pipeline health reported non-critical Data Quality warnings.")

    res = {
        "status": overall_freshness_status,
        "quality_status": quality_status,
        "checked_at": now_utc,
        "latest_station_status_snapshot_at": snapshot_ts,
        "station_status_lag_minutes": round(snapshot_lag_min, 1) if snapshot_lag_min is not None else None,
        "latest_hourly_mart_at": hourly_ts,
        "hourly_mart_lag_minutes": round(hourly_lag_min, 1) if hourly_lag_min is not None else None,
        "latest_daily_summary_date": daily_date,
        "latest_pipeline_health_status": health_status or "UNKNOWN",
        "latest_successful_dag_runs": dag_runs,
        "warnings": warnings,
    }
    _FRESHNESS_CACHE = res
    _FRESHNESS_CACHE_TIME = now_mono
    try:
        from api.cache import set_cache
        set_cache("bike_api:freshness_summary", res, ttl_seconds=15)
    except Exception as e:
        logger.debug(f"Failed to set Redis cache: {e}")
    return res
