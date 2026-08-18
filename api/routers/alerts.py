"""
FastAPI router for read-only Alert events.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query

from api.cache import get_cache, set_cache, make_cache_key
from api.dependencies import pagination_params, validate_sort_params
from api.response import DataResponse, ListResponse, make_data_response, make_list_response
from api.schemas import AlertEvent, AlertStats
from api.services.alert_service import (
    ALLOWED_ALERT_SORT_FIELDS,
    get_active_alerts,
    get_alert_history,
    get_alert_stats,
    get_latest_alerts,
)

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("/stats", response_model=DataResponse[AlertStats])
def get_alerts_stats_endpoint():
    """Lấy thống kê số lượng active alerts phân loại theo severity."""
    cache_key = "alerts:stats"
    cached = get_cache(cache_key)
    if cached is not None:
        return make_data_response(cached)

    stats = get_alert_stats()
    set_cache(cache_key, stats, ttl_seconds=15)
    return make_data_response(stats)


@router.get("/latest", response_model=DataResponse[List[AlertEvent]])
def get_latest_alerts_endpoint(
    limit: int = Query(20, ge=1, le=100, description="Max number of latest alerts to return"),
):
    """Lấy danh sách các alert mới nhất được ghi nhận trong hệ thống."""
    cache_key = make_cache_key("alerts:latest", limit=limit)
    cached = get_cache(cache_key)
    if cached is not None:
        return make_data_response(cached)

    records = get_latest_alerts(limit=limit)
    set_cache(cache_key, records, ttl_seconds=15)
    return make_data_response(records)


@router.get("/active", response_model=DataResponse[List[AlertEvent]])
def get_active_alerts_endpoint(
    limit: int = Query(50, ge=1, le=200, description="Max number of active alerts to return"),
):
    """Lấy danh sách các alert đang ở trạng thái OPEN hoặc FAILED_TO_SEND."""
    cache_key = make_cache_key("alerts:active", limit=limit)
    cached = get_cache(cache_key)
    if cached is not None:
        return make_data_response(cached)

    records = get_active_alerts(limit=limit)
    set_cache(cache_key, records, ttl_seconds=15)
    return make_data_response(records)


@router.get("/history", response_model=ListResponse[AlertEvent])
def get_alert_history_endpoint(
    severity: Optional[str] = Query(None, description="Optional severity filter (INFO, WARNING, ERROR, CRITICAL)"),
    status: Optional[str] = Query(None, description="Optional status filter (OPEN, SENT, FAILED_TO_SEND, RESOLVED, SKIPPED)"),
    alert_type: Optional[str] = Query(None, description="Optional alert type filter"),
    dag_id: Optional[str] = Query(None, description="Optional DAG ID filter"),
    sort_by: Optional[str] = Query("created_at", description="Sort field (created_at, severity, status, alert_type, dag_id)"),
    sort_order: str = Query("desc", description="Sort order (asc, desc)"),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    """Lấy lịch sử tất cả alerts có phân trang và lọc theo tiêu chí."""
    sort_col, mapped_order = validate_sort_params(sort_by, sort_order, ALLOWED_ALERT_SORT_FIELDS)
    limit, offset = pagination

    cache_key = make_cache_key(
        "alerts:history",
        severity=severity,
        status=status,
        alert_type=alert_type,
        dag_id=dag_id,
        sort=sort_col,
        order=mapped_order,
        limit=limit,
        offset=offset,
    )
    cached = get_cache(cache_key)
    if cached is not None:
        return make_list_response(cached["data"], count=cached["count"], limit=limit, offset=offset)

    records, total_count = get_alert_history(
        limit=limit,
        offset=offset,
        severity=severity,
        status=status,
        alert_type=alert_type,
        dag_id=dag_id,
        sort_column=sort_col,
        sort_order=mapped_order,
    )

    set_cache(cache_key, {"data": records, "count": total_count}, ttl_seconds=30)
    return make_list_response(records, count=total_count, limit=limit, offset=offset)
