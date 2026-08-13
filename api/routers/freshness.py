from fastapi import APIRouter

from api.cache import get_cache, make_cache_key, set_cache
from api.response import DataResponse, make_data_response
from api.schemas import DataFreshnessSummary
from api.services.freshness_service import get_data_freshness_summary

router = APIRouter(prefix="/freshness", tags=["Data Freshness"])


@router.get("/summary", response_model=DataResponse[DataFreshnessSummary])
def get_freshness_summary():
    """
    Get comprehensive data freshness and pipeline currency summary.

    Evaluates latency across:
    - Real-time station status snapshot ingestion
    - Hourly mobility data marts
    - Daily aggregated summaries
    - Airflow DAG execution statuses
    """
    cache_key = make_cache_key("freshness:summary")
    cached = get_cache(cache_key)
    if cached is not None:
        return make_data_response(cached)

    freshness_data = get_data_freshness_summary()
    set_cache(cache_key, freshness_data, ttl_seconds=15)
    return make_data_response(freshness_data)
