from typing import Optional

from src.common.db import execute_sql, fetch_one
from src.common.logger import get_logger

logger = get_logger(__name__)


def get_watermark(source_name: str) -> Optional[str]:
    """
    Get the latest successful watermark value for a given source.

    Returns None if the source has no watermark yet.
    """
    sql = """
        SELECT last_successful_value
        FROM etl_metadata.watermarks
        WHERE source_name = :source_name
    """

    result = fetch_one(
        sql,
        {
            "source_name": source_name,
        },
    )

    if not result:
        return None

    return result["last_successful_value"]


def update_watermark(source_name: str, last_successful_value: str) -> None:
    """
    Upsert the watermark value for a given source.

    This should be called only after the related pipeline step
    has completed successfully.
    """
    logger.info(
        f"Updating watermark for source '{source_name}' "
        f"to '{last_successful_value}'"
    )

    sql = """
        INSERT INTO etl_metadata.watermarks (
            source_name,
            last_successful_value,
            updated_at
        ) VALUES (
            :source_name,
            :last_successful_value,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (source_name) DO UPDATE SET
            last_successful_value = EXCLUDED.last_successful_value,
            updated_at = EXCLUDED.updated_at
    """

    execute_sql(
        sql,
        {
            "source_name": source_name,
            "last_successful_value": last_successful_value,
        },
    )