import os
from typing import Any, Dict, List, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from src.common.config import get_settings
from src.common.logger import get_logger

logger = get_logger(__name__)

# Cached SQLAlchemy engine
_engine: Optional[Engine] = None

def get_engine() -> Engine:
    """
    Get or create the SQLAlchemy engine. Uses lazy initialization to prevent
    connections during code import.
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        # Prioritize DATABASE_URL from actual environment over env_file settings
        db_url = os.getenv("DATABASE_URL", settings.DATABASE_URL)
        logger.info("Initializing SQLAlchemy database engine...")
        _engine = create_engine(db_url, pool_pre_ping=True)
    return _engine

def execute_sql(sql: str, params: Optional[Dict[str, Any]] = None) -> None:
    """
    Execute a non-query SQL command (INSERT, UPDATE, DELETE, DDL).
    Uses a transaction block (begin) which commits automatically on success.
    """
    engine = get_engine()
    try:
        with engine.begin() as conn:
            conn.execute(text(sql), params or {})
    except Exception as e:
        logger.error(f"Failed to execute SQL: {e}")
        logger.debug(f"SQL statement: {sql} | Params: {params}")
        raise e

def fetch_all(sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Execute a query and fetch all resulting rows as a list of dictionaries.
    """
    engine = get_engine()
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            return [dict(row) for row in result.mappings()]
    except Exception as e:
        logger.error(f"Failed to fetch all from SQL: {e}")
        logger.debug(f"SQL statement: {sql} | Params: {params}")
        raise e

def fetch_one(sql: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Execute a query and fetch the first matching row as a dictionary, or None if empty.
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
        raise e

def execute_sql_file(path: str, params: Optional[Dict[str, Any]] = None) -> None:
    """
    Read a SQL script file from the given path and execute its content.
    """
    logger.info(f"Executing database SQL script from file: {path}")
    try:
        with open(path, "r", encoding="utf-8") as file:
            sql_content = file.read()
        execute_sql(sql_content, params)
    except Exception as e:
        logger.error(f"Failed to execute SQL file '{path}': {e}")
        raise e
