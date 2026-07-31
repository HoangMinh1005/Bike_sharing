from typing import Any, List
from fastapi import APIRouter, Query

from api.cache import get_cache, set_cache, make_cache_key
from api.dependencies import validate_health_status
from api.response import DataResponse, make_data_response
from api.schemas import PipelineHealth
from api.services.pipeline_service import (
    get_latest_pipeline_health,
    get_pipeline_health_history,
    get_pipeline_health_by_status,
    get_latest_pipeline_runs,
)

router = APIRouter(prefix="/pipelines", tags=["Pipeline Health & Metadata"])


@router.get("/health/latest", response_model=DataResponse[List[PipelineHealth]])
def get_pipelines_health_latest():
    """Lấy trạng thái sức khỏe tổng hợp mới nhất của tất cả các pipeline."""
    cache_key = make_cache_key("pipelines:health:latest")
    cached = get_cache(cache_key)
    if cached is not None:
        return make_data_response(cached)

    records = get_latest_pipeline_health()
    set_cache(cache_key, records, ttl_seconds=60)
    return make_data_response(records)


@router.get("/health/status/{health_status}", response_model=DataResponse[List[PipelineHealth]])
def get_pipelines_health_status(health_status: str):
    """Lọc danh sách các pipeline theo trạng thái sức khỏe (HEALTHY, WARNING, FAILED, STALE, UNKNOWN)."""
    valid_status = validate_health_status(health_status)
    cache_key = make_cache_key("pipelines:health:status", status=valid_status)
    cached = get_cache(cache_key)
    if cached is not None:
        return make_data_response(cached)

    records = get_pipeline_health_by_status(health_status=valid_status)
    set_cache(cache_key, records, ttl_seconds=60)
    return make_data_response(records)


@router.get("/health/{dag_id}", response_model=DataResponse[List[PipelineHealth]])
def get_pipeline_health_by_dag(
    dag_id: str,
    limit: int = Query(24, ge=1, le=100, description="Number of historical health runs to fetch"),
):
    """Lấy lịch sử kiểm tra sức khỏe của một DAG cụ thể."""
    cache_key = make_cache_key("pipelines:health:dag", dag_id=dag_id, limit=limit)
    cached = get_cache(cache_key)
    if cached is not None:
        return make_data_response(cached)

    records = get_pipeline_health_history(dag_id=dag_id, limit=limit)
    set_cache(cache_key, records, ttl_seconds=60)
    return make_data_response(records)


@router.get("/runs/latest", response_model=DataResponse[List[Any]])
def get_pipelines_runs_latest():
    """Lấy đợt thực thi (run execution) mới nhất của từng pipeline từ etl_metadata.pipeline_runs."""
    cache_key = make_cache_key("pipelines:runs:latest")
    cached = get_cache(cache_key)
    if cached is not None:
        return make_data_response(cached)

    records = get_latest_pipeline_runs()
    set_cache(cache_key, records, ttl_seconds=60)
    return make_data_response(records)
