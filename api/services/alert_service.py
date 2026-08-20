"""
Service layer for read-only Alert queries.
"""
from typing import Any, Dict, List, Optional, Tuple
from src.common.db import fetch_all, fetch_one
from src.common.logger import get_logger

logger = get_logger(__name__)

ALLOWED_ALERT_SORT_FIELDS = {
    "created_at": "created_at",
    "severity": "severity",
    "status": "status",
    "alert_type": "alert_type",
    "dag_id": "dag_id",
}


def _format_alert_row(row: dict) -> dict:
    """Format single alert DB row into API schema compatible dict."""
    if not row:
        return {}
    res = dict(row)
    if "alert_id" in res and res["alert_id"] is not None:
        res["alert_id"] = str(res["alert_id"])
    return res


def get_latest_alerts(limit: int = 20) -> List[dict]:
    """
    Retrieve the most recent alert events.
    """
    try:
        query = """
            SELECT *
            FROM etl_metadata.alert_events
            ORDER BY created_at DESC
            LIMIT :limit
        """
        rows = fetch_all(query, {"limit": limit})
        return [_format_alert_row(r) for r in rows]
    except Exception as e:
        logger.warning(f"Error fetching latest alerts (returning empty list): {e}")
        return []


def get_active_alerts(limit: int = 50) -> List[dict]:
    """
    Retrieve currently active alert events (OPEN or FAILED_TO_SEND)
    along with recently RESOLVED alerts from the last 24 hours.
    Unresolved alerts persist indefinitely; resolved alerts disappear after 24h.
    """
    try:
        query = """
            SELECT *
            FROM etl_metadata.alert_events
            WHERE status IN ('OPEN', 'FAILED_TO_SEND')
               OR (
                   status = 'RESOLVED'
                   AND (
                       resolved_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                       OR created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                   )
               )
            ORDER BY
                CASE WHEN status IN ('OPEN', 'FAILED_TO_SEND') THEN 0 ELSE 1 END ASC,
                created_at DESC
            LIMIT :limit
        """
        rows = fetch_all(query, {"limit": limit})
        return [_format_alert_row(r) for r in rows]
    except Exception as e:
        logger.warning(f"Error fetching active alerts (returning empty list): {e}")
        return []


def get_alert_history(
    limit: int = 20,
    offset: int = 0,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    alert_type: Optional[str] = None,
    dag_id: Optional[str] = None,
    sort_column: str = "created_at",
    sort_order: str = "desc",
) -> Tuple[List[dict], int]:
    """
    Retrieve paginated alert history with filtering.
    """
    where_clauses = ["1=1"]
    params: Dict[str, Any] = {"limit": limit, "offset": offset}

    if severity:
        where_clauses.append("severity = :severity")
        params["severity"] = severity.upper()
    if status:
        where_clauses.append("status = :status")
        params["status"] = status.upper()
    if alert_type:
        where_clauses.append("alert_type = :alert_type")
        params["alert_type"] = alert_type
    if dag_id:
        where_clauses.append("dag_id = :dag_id")
        params["dag_id"] = dag_id

    where_sql = " AND ".join(where_clauses)
    order_by_col = ALLOWED_ALERT_SORT_FIELDS.get(sort_column, "created_at")
    sort_direction = "DESC" if sort_order.lower() == "desc" else "ASC"

    try:
        count_query = f"""
            SELECT COUNT(*) AS count
            FROM etl_metadata.alert_events
            WHERE {where_sql}
        """
        count_row = fetch_one(count_query, params)
        total_count = int(count_row["count"]) if count_row else 0

        data_query = f"""
            SELECT *
            FROM etl_metadata.alert_events
            WHERE {where_sql}
            ORDER BY {order_by_col} {sort_direction}
            LIMIT :limit OFFSET :offset
        """
        rows = fetch_all(data_query, params)
        return [_format_alert_row(r) for r in rows], total_count
    except Exception as e:
        logger.warning(f"Error fetching alert history (returning empty): {e}")
        return [], 0


def get_alert_stats() -> dict:
    """
    Calculate summary count statistics for active alerts grouped by severity,
    plus the count of resolved alerts in the last 24 hours.
    """
    default_stats = {
        "total_active": 0,
        "critical_count": 0,
        "error_count": 0,
        "warning_count": 0,
        "info_count": 0,
        "resolved_count": 0,
    }
    try:
        query = """
            SELECT
                COUNT(*) FILTER (WHERE status IN ('OPEN', 'FAILED_TO_SEND')) AS total_active,
                COUNT(*) FILTER (WHERE status IN ('OPEN', 'FAILED_TO_SEND') AND severity = 'CRITICAL') AS critical_count,
                COUNT(*) FILTER (WHERE status IN ('OPEN', 'FAILED_TO_SEND') AND severity = 'ERROR') AS error_count,
                COUNT(*) FILTER (WHERE status IN ('OPEN', 'FAILED_TO_SEND') AND severity = 'WARNING') AS warning_count,
                COUNT(*) FILTER (WHERE status IN ('OPEN', 'FAILED_TO_SEND') AND severity = 'INFO') AS info_count,
                COUNT(*) FILTER (
                    WHERE status = 'RESOLVED'
                    AND (
                        resolved_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                        OR created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                    )
                ) AS resolved_count
            FROM etl_metadata.alert_events
        """
        row = fetch_one(query)
        if row:
            return {
                "total_active": int(row.get("total_active") or 0),
                "critical_count": int(row.get("critical_count") or 0),
                "error_count": int(row.get("error_count") or 0),
                "warning_count": int(row.get("warning_count") or 0),
                "info_count": int(row.get("info_count") or 0),
                "resolved_count": int(row.get("resolved_count") or 0),
            }
        return default_stats
    except Exception as e:
        logger.warning(f"Error fetching alert stats: {e}")
        return default_stats
