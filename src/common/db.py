from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.common.config import get_settings
from src.common.logger import get_logger

logger = get_logger(__name__)

_engine: Optional[Engine] = None


def get_engine() -> Engine:
    """
    Get or create the SQLAlchemy engine.
    Uses lazy initialization to prevent database connections during import.
    """
    global _engine

    if _engine is None:
        settings = get_settings()
        db_url = settings.DATABASE_URL

        logger.info("Initializing SQLAlchemy database engine...")
        _engine = create_engine(db_url, pool_pre_ping=True)

    return _engine


def execute_sql(sql: str, params: Optional[Dict[str, Any]] = None) -> int:
    """
    Execute a non-query SQL command: INSERT, UPDATE, DELETE, DDL.
    Returns the number of affected rows when available.
    """
    engine = get_engine()

    try:
        with engine.begin() as conn:
            result = conn.execute(text(sql), params or {})
            return result.rowcount if result.rowcount is not None else 0

    except Exception as e:
        logger.error(f"Failed to execute SQL: {e}")
        logger.debug(f"SQL statement: {sql} | Params: {params}")
        raise


def fetch_all(sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Execute a query and fetch all rows as a list of dictionaries.
    """
    engine = get_engine()

    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            return [dict(row) for row in result.mappings()]

    except Exception as e:
        logger.error(f"Failed to fetch all from SQL: {e}")
        logger.debug(f"SQL statement: {sql} | Params: {params}")
        raise


def fetch_one(sql: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Execute a query and fetch the first row as a dictionary.
    Return None if no row exists.
    """
    engine = get_engine()

    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            row = result.mappings().first()
            return dict(row) if row else None

    except Exception as e:
        logger.error(f"Failed to fetch one from SQL: {e}")
        logger.debug(f"SQL statement: {sql} | Params: {params}")
        raise


def execute_sql_file(path: str, params: Optional[Dict[str, Any]] = None) -> int:
    """
    Read a SQL file and execute its content.
    Suitable for normal SQL scripts such as CREATE TABLE, INSERT, UPDATE.
    """
    logger.info(f"Executing SQL file: {path}")

    try:
        with open(path, "r", encoding="utf-8") as file:
            sql_content = file.read()

        return execute_sql(sql_content, params)

    except Exception as e:
        logger.error(f"Failed to execute SQL file '{path}': {e}")
        raise