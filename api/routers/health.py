from fastapi import APIRouter

from api.response import DataResponse, make_data_response
from api.schemas import ApiHealth
from api.services.health_service import check_api_health

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=DataResponse[ApiHealth])
def get_health():
    """Kiểm tra sức khỏe dịch vụ API, kết nối PostgreSQL và Redis."""
    health_data = check_api_health()
    return make_data_response(health_data)
