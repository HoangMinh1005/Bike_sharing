from typing import Any, Dict, Generic, List, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """
    Pagination metadata for list responses.

    count:
        Number of records returned in the current response.

    limit:
        Maximum number of records requested.

    offset:
        Number of records skipped.
    """

    count: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
    offset: int = Field(..., ge=0)


class ListResponse(BaseModel, Generic[T]):
    """
    Standard list response wrapper.
    """

    data: List[T]
    meta: PaginationMeta


class DataResponse(BaseModel, Generic[T]):
    """
    Standard single-object response wrapper.
    """

    data: T


class ErrorDetail(BaseModel):
    """
    Standard error detail object.
    """

    code: str
    message: str


class ErrorResponse(BaseModel):
    """
    Standard error response wrapper.
    """

    error: ErrorDetail


def make_list_response(
    data: List[Any],
    count: int,
    limit: int,
    offset: int,
) -> Dict[str, Any]:
    """
    Format standardized JSON list response with pagination metadata.

    count represents the number of records returned in this response,
    not necessarily the total number of records in the database.
    """
    return {
        "data": data,
        "meta": {
            "count": int(count),
            "limit": int(limit),
            "offset": int(offset),
        },
    }


def make_data_response(data: Any) -> Dict[str, Any]:
    """
    Format standardized JSON object response wrapper.
    """
    return {
        "data": data,
    }


def make_error_response(code: str, message: str) -> Dict[str, Any]:
    """
    Format standardized JSON error response wrapper.
    """
    return {
        "error": {
            "code": code,
            "message": message,
        }
    }