"""
Prometheus Metrics Integration for GBFS Bike Sharing Operation Intelligence API.
Exposes HTTP request metrics and reuses existing Data Freshness logic to expose SLA/SLO gauges.
"""
import re
import time
from typing import Dict

from fastapi import Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from api.services.freshness_service import get_data_freshness_summary
from src.common.db import fetch_one
from src.common.logger import get_logger

logger = get_logger(__name__)

# Numeric mapping for categorical health statuses
STATUS_NUMERIC_MAP: Dict[str, float] = {
    "UNKNOWN": 0.0,
    "HEALTHY": 1.0,
    "LIVE": 1.0,
    "WARNING": 2.0,
    "STALE": 3.0,
    "FAILED": 4.0,
}


# ----------------------------------------------------
# Prometheus Metric Definitions
# ----------------------------------------------------

# HTTP Metrics
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total count of HTTP requests handled by FastAPI",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency histogram in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently being processed",
    ["method", "endpoint"],
)

# GBFS Data Freshness & SLA Gauges (reusing freshness_service.py)
GBFS_STATION_STATUS_LAG_MINUTES = Gauge(
    "gbfs_station_status_freshness_lag_minutes",
    "Lag in minutes for the latest station_status snapshot",
)

GBFS_HOURLY_MART_LAG_MINUTES = Gauge(
    "gbfs_hourly_mart_freshness_lag_minutes",
    "Lag in minutes for the latest hourly mobility data mart",
)

GBFS_DAILY_SUMMARY_CURRENT = Gauge(
    "gbfs_daily_summary_current",
    "Daily summary freshness indicator (1 = HEALTHY/CURRENT, 0 = STALE/MISSING)",
)

GBFS_PIPELINE_HEALTH_STATUS = Gauge(
    "gbfs_pipeline_health_status",
    "Overall pipeline health summary status (1=HEALTHY, 2=WARNING, 3=STALE, 4=FAILED, 0=UNKNOWN)",
)

GBFS_DATA_FRESHNESS_STATUS = Gauge(
    "gbfs_data_freshness_status",
    "Overall data currency status (1=HEALTHY, 2=WARNING, 3=STALE, 4=FAILED, 0=UNKNOWN)",
)

GBFS_DAG_LATEST_SUCCESS_LAG_MINUTES = Gauge(
    "gbfs_dag_latest_success_lag_minutes",
    "Lag in minutes since the latest successful run of an Airflow DAG",
    ["dag_id"],
)

# Data Quality & Self-Healing Metrics
GBFS_DQ_FAILED_TOTAL = Gauge(
    "gbfs_dq_failed_total",
    "Total count of failed Data Quality check executions in etl_metadata",
)

GBFS_DQ_WARNING_TOTAL = Gauge(
    "gbfs_dq_warning_total",
    "Total count of warning Data Quality check executions in etl_metadata",
)

GBFS_DQ_SELF_HEALED_TOTAL = Gauge(
    "gbfs_dq_self_healed_total",
    "Total count of self-healed metadata drift occurrences recorded in etl_metadata",
)


# ----------------------------------------------------
# Route Path Normalization (Cardinality Protection)
# ----------------------------------------------------
def normalize_route_path(path: str) -> str:
    """
    Normalize URL paths to prevent high cardinality metric labels in Prometheus.
    Replaces dynamic IDs and UUIDs with route template placeholders.
    """
    if not path:
        return "unknown"

    # Known route patterns
    p = path.rstrip("/")
    if p in ("", "/"):
        return "/"
    if p == "/metrics":
        return "/metrics"
    if p == "/docs" or p == "/redoc" or p == "/openapi.json":
        return p

    # Standardize /api/v1 routes
    # e.g., /api/v1/stations/31200/history -> /api/v1/stations/{station_id}/history
    p = re.sub(r"/api/v1/stations/[^/]+/history", "/api/v1/stations/{station_id}/history", p)
    p = re.sub(r"/api/v1/stations/[^/]+/daily", "/api/v1/stations/{station_id}/daily", p)
    p = re.sub(r"/api/v1/stations/[^/]+", "/api/v1/stations/{station_id}", p)

    p = re.sub(r"/api/v1/regions/[^/]+/history", "/api/v1/regions/{region_id}/history", p)
    p = re.sub(r"/api/v1/regions/[^/]+", "/api/v1/regions/{region_id}", p)

    # General fallback for UUIDs or numeric IDs
    p = re.sub(r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", "/{id}", p)
    p = re.sub(r"/\d+", "/{id}", p)

    return p


# ----------------------------------------------------
# Metrics Scrape Update Handler
# ----------------------------------------------------
def update_freshness_prometheus_metrics() -> None:
    """
    Safely update Prometheus Gauge metrics by reusing existing get_freshness_summary() service.
    Guaranteed not to raise exceptions to protect /metrics endpoint availability.
    """
    try:
        freshness_data = get_data_freshness_summary()

        # 1. Station Status Snapshot Lag
        station_lag = freshness_data.get("station_status_lag_minutes")
        if station_lag is not None:
            GBFS_STATION_STATUS_LAG_MINUTES.set(float(station_lag))

        # 2. Hourly Mart Lag
        hourly_lag = freshness_data.get("hourly_mart_lag_minutes")
        if hourly_lag is not None:
            GBFS_HOURLY_MART_LAG_MINUTES.set(float(hourly_lag))

        # 3. Daily Summary Current Indicator
        daily_date = freshness_data.get("latest_daily_summary_date")
        GBFS_DAILY_SUMMARY_CURRENT.set(1.0 if daily_date is not None else 0.0)

        # 4. Pipeline Health & Overall Data Freshness Status
        pipeline_status = str(freshness_data.get("latest_pipeline_health_status", "UNKNOWN")).upper()
        GBFS_PIPELINE_HEALTH_STATUS.set(STATUS_NUMERIC_MAP.get(pipeline_status, 0.0))

        overall_status = str(freshness_data.get("status", "UNKNOWN")).upper()
        GBFS_DATA_FRESHNESS_STATUS.set(STATUS_NUMERIC_MAP.get(overall_status, 0.0))


        # 5. DAG Execution Lags
        dag_runs = freshness_data.get("latest_successful_dag_runs", [])
        for dag_info in dag_runs:
            dag_id = dag_info.get("dag_id")
            dag_lag = dag_info.get("lag_minutes")
            if dag_id and dag_lag is not None:
                GBFS_DAG_LATEST_SUCCESS_LAG_MINUTES.labels(dag_id=dag_id).set(float(dag_lag))

    except Exception as e:
        logger.warning(f"Error updating freshness Prometheus metrics: {e}")

    # Safely query Data Quality & Self-Healing stats from etl_metadata
    try:
        dq_counts = fetch_one(
            """
            SELECT
                COALESCE(SUM(CASE WHEN LOWER(status) = 'failed' THEN 1 ELSE 0 END), 0) AS failed_cnt,
                COALESCE(SUM(CASE WHEN LOWER(status) = 'warning' THEN 1 ELSE 0 END), 0) AS warning_cnt,
                COALESCE(SUM(CASE WHEN message LIKE '%[SELF_HEALED]%' OR message LIKE '%Self-healed%' THEN 1 ELSE 0 END), 0) AS self_healed_cnt
            FROM etl_metadata.dq_results
            """
        )
        if dq_counts:
            GBFS_DQ_FAILED_TOTAL.set(float(dq_counts.get("failed_cnt", 0)))
            GBFS_DQ_WARNING_TOTAL.set(float(dq_counts.get("warning_cnt", 0)))
            GBFS_DQ_SELF_HEALED_TOTAL.set(float(dq_counts.get("self_healed_cnt", 0)))
    except Exception as e:
        logger.debug(f"Error updating DQ Prometheus metrics: {e}")


# ----------------------------------------------------
# FastAPI Metrics Endpoint & Middleware Handler
# ----------------------------------------------------
async def prometheus_metrics_middleware(request: Request, call_next):
    """FastAPI Middleware to measure HTTP request rate, latency, and status code counts."""
    # Exclude /metrics endpoint and OPTIONS preflight requests from metrics recording
    if request.url.path == "/metrics" or request.method == "OPTIONS":
        return await call_next(request)


    endpoint = normalize_route_path(request.url.path)
    method = request.method

    HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()
    start_time = time.time()

    try:
        response = await call_next(request)
        status_code = str(response.status_code)
    except Exception:
        status_code = "500"
        raise
    finally:
        duration = time.time() - start_time
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()
        HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=endpoint).observe(duration)

    return response


async def handle_metrics_endpoint(request: Request) -> Response:
    """Endpoint handler for GET /metrics scraped by Prometheus."""
    update_freshness_prometheus_metrics()
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
