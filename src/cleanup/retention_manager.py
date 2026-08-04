import copy
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import pendulum

from src.common.db import execute_sql, fetch_one
from src.common.logger import get_logger

logger = get_logger(__name__)

DEFAULT_DELETE_BATCH_SIZE = 10_000
MAX_DELETE_BATCH_SIZE = 100_000
DEFAULT_MAX_BATCHES = 100_000

_QUALIFIED_TABLE_PATTERN = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$"
)
_COLUMN_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


# Default retention policies for Bike Sharing Operation Intelligence.
#
# Design notes:
# - All retention cutoffs use one UTC reference time per cleanup run.
# - Dynamic raw/staging data is kept for 45 days to support a 31-day
#   backfill window plus operational buffer.
# - Metadata/detail tables are cleaned before pipeline_runs to reduce
#   the risk of foreign-key issues.
# - Mart retention is disabled by default because mart tables serve API/dashboard.
# - Watermarks are intentionally not included by default.
RETENTION_POLICIES: List[Dict[str, Any]] = [
    {
        "table_name": "raw.gbfs_feed_snapshots",
        "timestamp_column": "fetched_at",
        "retention_days": 30,
        "enabled": True,
    },
    {
        "table_name": "raw.station_status_snapshots",
        "timestamp_column": "fetched_at",
        "retention_days": 45,
        "enabled": True,
    },
    {
        "table_name": "raw.weather_hourly",
        "timestamp_column": "fetched_at",
        "retention_days": 45,
        "enabled": True,
    },
    {
        "table_name": "raw.calendar",
        "timestamp_column": "loaded_at",
        "retention_days": 400,
        "enabled": True,
    },
    {
        "table_name": "staging.station_vehicle_type_status",
        "timestamp_column": "fetched_at",
        "retention_days": 45,
        "enabled": True,
    },
    {
        "table_name": "staging.station_status",
        "timestamp_column": "fetched_at",
        "retention_days": 45,
        "enabled": True,
    },
    {
        "table_name": "staging.weather_hourly",
        "timestamp_column": "fetched_at",
        "retention_days": 90,
        "enabled": True,
    },
    {
        "table_name": "staging.calendar",
        "timestamp_column": "updated_at",
        "retention_days": 400,
        "enabled": True,
    },
    {
        "table_name": "etl_metadata.dq_results",
        "timestamp_column": "checked_at",
        "retention_days": 90,
        "enabled": True,
    },
    {
        "table_name": "etl_metadata.rejected_records",
        "timestamp_column": "created_at",
        "retention_days": 90,
        "enabled": True,
    },
    {
        "table_name": "etl_metadata.pipeline_health_summary",
        "timestamp_column": "checked_at",
        "retention_days": 90,
        "enabled": True,
    },
    {
        "table_name": "etl_metadata.pipeline_runs",
        "timestamp_column": "started_at",
        "retention_days": 180,
        "enabled": True,
    },
    # Mart retention is disabled by default.
    # Only enable these after confirming dashboard/API history requirements.
    {
        "table_name": "mart.hourly_station_availability",
        "timestamp_column": "hour_bucket",
        "retention_days": 365,
        "enabled": False,
    },
    {
        "table_name": "mart.daily_station_summary",
        "timestamp_column": "summary_date",
        "retention_days": 730,
        "enabled": False,
    },
]


def get_retention_policies() -> List[Dict[str, Any]]:
    """
    Return a deep copy of configured retention policies.

    Returning a copy prevents callers from mutating the global policy list.
    """
    return copy.deepcopy(RETENTION_POLICIES)


def _validate_retention_policy(policy: Dict[str, Any]) -> None:
    """
    Validate one retention policy.

    This validates both business fields and SQL identifier format.
    """
    if not isinstance(policy, dict) or not policy:
        raise ValueError("Retention policy must be a non-empty dictionary.")

    table_name = policy.get("table_name")
    timestamp_column = policy.get("timestamp_column")
    retention_days = policy.get("retention_days")
    enabled = policy.get("enabled")
    delete_batch_size = policy.get(
        "delete_batch_size",
        DEFAULT_DELETE_BATCH_SIZE,
    )

    if not isinstance(table_name, str) or not table_name.strip():
        raise ValueError("Retention policy is missing a valid table_name.")

    clean_table = table_name.strip()

    if not _QUALIFIED_TABLE_PATTERN.fullmatch(clean_table):
        raise ValueError(
            f"Invalid table_name '{clean_table}'. "
            "Expected schema.table using standard SQL identifiers."
        )

    if not isinstance(timestamp_column, str) or not timestamp_column.strip():
        raise ValueError(
            f"Retention policy for '{clean_table}' is missing "
            "a valid timestamp_column."
        )

    clean_column = timestamp_column.strip()

    if not _COLUMN_PATTERN.fullmatch(clean_column):
        raise ValueError(
            f"Invalid timestamp_column '{clean_column}' "
            f"for table '{clean_table}'."
        )

    if (
        isinstance(retention_days, bool)
        or not isinstance(retention_days, int)
        or retention_days <= 0
    ):
        raise ValueError(
            f"Retention policy for '{clean_table}' must have "
            "retention_days as a positive integer."
        )

    if not isinstance(enabled, bool):
        raise ValueError(
            f"Retention policy for '{clean_table}' must have "
            "enabled as a boolean."
        )

    if (
        isinstance(delete_batch_size, bool)
        or not isinstance(delete_batch_size, int)
        or delete_batch_size <= 0
        or delete_batch_size > MAX_DELETE_BATCH_SIZE
    ):
        raise ValueError(
            f"Retention policy for '{clean_table}' must have "
            f"delete_batch_size between 1 and {MAX_DELETE_BATCH_SIZE}."
        )


def _validate_cleanup_arguments(
    table_name: Any,
    timestamp_column: Any,
    retention_days: Any,
    dry_run: Any,
    allow_disabled: Any,
    max_batches: Any,
) -> None:
    """
    Validate public cleanup function arguments.
    """
    if not isinstance(table_name, str) or not table_name.strip():
        raise ValueError("table_name must be a non-empty string.")

    if not isinstance(timestamp_column, str) or not timestamp_column.strip():
        raise ValueError("timestamp_column must be a non-empty string.")

    if (
        isinstance(retention_days, bool)
        or not isinstance(retention_days, int)
        or retention_days <= 0
    ):
        raise ValueError("retention_days must be a positive integer.")

    if not isinstance(dry_run, bool):
        raise ValueError("dry_run must be a boolean.")

    if not isinstance(allow_disabled, bool):
        raise ValueError("allow_disabled must be a boolean.")

    if (
        isinstance(max_batches, bool)
        or not isinstance(max_batches, int)
        or max_batches <= 0
    ):
        raise ValueError("max_batches must be a positive integer.")


def _is_allowed_retention_target(
    table_name: str,
    timestamp_column: str,
    retention_days: int,
) -> bool:
    """
    Check whether a cleanup target exactly matches RETENTION_POLICIES.

    table_name and timestamp_column cannot be passed as SQL bind parameters.
    Therefore they must come from a source-controlled whitelist.
    """
    clean_table = table_name.strip()
    clean_column = timestamp_column.strip()

    for policy in RETENTION_POLICIES:
        if (
            policy.get("table_name") == clean_table
            and policy.get("timestamp_column") == clean_column
            and policy.get("retention_days") == retention_days
        ):
            _validate_retention_policy(policy)
            return True

    return False


def _find_retention_policy(
    table_name: str,
    timestamp_column: str,
    retention_days: int,
) -> Dict[str, Any]:
    """
    Return a deep copy of the exact whitelisted retention policy.
    """
    if not _is_allowed_retention_target(
        table_name=table_name,
        timestamp_column=timestamp_column,
        retention_days=retention_days,
    ):
        raise ValueError(
            "Unauthorized retention cleanup target: "
            f"table_name='{table_name}', "
            f"timestamp_column='{timestamp_column}', "
            f"retention_days={retention_days}. "
            "The target does not exactly match RETENTION_POLICIES."
        )

    clean_table = table_name.strip()
    clean_column = timestamp_column.strip()

    for policy in RETENTION_POLICIES:
        if (
            policy.get("table_name") == clean_table
            and policy.get("timestamp_column") == clean_column
            and policy.get("retention_days") == retention_days
        ):
            return copy.deepcopy(policy)

    raise ValueError(
        f"Retention policy not found for table '{clean_table}'."
    )


def _normalize_reference_time(
    reference_time: Optional[Any],
) -> pendulum.DateTime:
    """
    Normalize reference_time to timezone-aware UTC pendulum DateTime.

    Supported input:
    - None
    - datetime.datetime
    - pendulum.DateTime
    - ISO datetime string
    """
    if reference_time is None:
        return pendulum.now("UTC")

    try:
        if isinstance(reference_time, pendulum.DateTime):
            parsed = reference_time
        elif isinstance(reference_time, datetime):
            if reference_time.tzinfo is None:
                parsed = pendulum.datetime(
                    reference_time.year,
                    reference_time.month,
                    reference_time.day,
                    reference_time.hour,
                    reference_time.minute,
                    reference_time.second,
                    reference_time.microsecond,
                    tz="UTC",
                )
            else:
                parsed = pendulum.instance(reference_time)
        elif isinstance(reference_time, str) and reference_time.strip():
            parsed = pendulum.parse(reference_time.strip())
        else:
            raise ValueError(
                "reference_time must be None, datetime, pendulum DateTime, "
                "or a non-empty ISO datetime string."
            )
    except Exception as exc:
        raise ValueError(
            f"Invalid reference_time '{reference_time}': {exc}"
        ) from exc

    if parsed.tzinfo is None:
        parsed = pendulum.datetime(
            parsed.year,
            parsed.month,
            parsed.day,
            parsed.hour,
            parsed.minute,
            parsed.second,
            parsed.microsecond,
            tz="UTC",
        )
    else:
        parsed = parsed.in_timezone("UTC")

    return parsed


def _quote_identifier(identifier: str) -> str:
    """
    Quote a validated PostgreSQL identifier.

    The identifier is already validated by regex, so it cannot contain quotes.
    """
    return f'"{identifier}"'


def _quote_qualified_table(table_name: str) -> str:
    """
    Quote a validated schema-qualified table name.
    """
    schema_name, relation_name = table_name.split(".", maxsplit=1)

    return (
        f"{_quote_identifier(schema_name)}."
        f"{_quote_identifier(relation_name)}"
    )


def _read_count_value(
    row: Any,
    key: str,
    default: int = 0,
) -> int:
    """
    Read an integer count from dict-like or row-like database result.
    """
    if row is None:
        return default

    try:
        value = row[key]
    except (KeyError, TypeError):
        value = getattr(row, key, default)

    return int(value or 0)


def cleanup_table_by_retention(
    table_name: str,
    timestamp_column: str,
    retention_days: int,
    dry_run: bool = False,
    allow_disabled: bool = False,
    reference_time: Optional[Any] = None,
    max_batches: int = DEFAULT_MAX_BATCHES,
) -> Dict[str, Any]:
    """
    Apply one configured retention policy.

    Safety rules:
    - table_name + timestamp_column + retention_days must exactly match
      RETENTION_POLICIES.
    - Disabled policies cannot delete data unless allow_disabled=True.
    - dry_run=True never deletes data.
    - SQL identifiers come only from the validated whitelist.
    - DELETE runs in batches to reduce lock duration and transaction size.
    """
    _validate_cleanup_arguments(
        table_name=table_name,
        timestamp_column=timestamp_column,
        retention_days=retention_days,
        dry_run=dry_run,
        allow_disabled=allow_disabled,
        max_batches=max_batches,
    )

    policy = _find_retention_policy(
        table_name=table_name,
        timestamp_column=timestamp_column,
        retention_days=retention_days,
    )

    if not policy["enabled"] and not dry_run and not allow_disabled:
        raise ValueError(
            f"Retention policy for '{table_name}' is disabled. "
            "Set allow_disabled=True only for explicitly approved deletion."
        )

    reference_dt = _normalize_reference_time(reference_time)
    cutoff_at = reference_dt.subtract(days=retention_days)

    clean_table = policy["table_name"]
    clean_column = policy["timestamp_column"]

    table_sql = _quote_qualified_table(clean_table)
    column_sql = _quote_identifier(clean_column)

    batch_size = int(
        policy.get("delete_batch_size", DEFAULT_DELETE_BATCH_SIZE)
    )

    if dry_run:
        count_sql = f"""
            SELECT
                COUNT(*) FILTER (
                    WHERE {column_sql} < :cutoff_at
                ) AS expired_count,
                COUNT(*) FILTER (
                    WHERE {column_sql} IS NULL
                ) AS null_timestamp_count
            FROM {table_sql}
        """

        row = fetch_one(
            count_sql,
            {"cutoff_at": cutoff_at},
        )

        rows_matched = _read_count_value(row, "expired_count")
        null_timestamp_rows = _read_count_value(
            row,
            "null_timestamp_count",
        )

        if null_timestamp_rows > 0:
            logger.warning(
                f"[DRY RUN] Table '{clean_table}' contains "
                f"{null_timestamp_rows} row(s) where '{clean_column}' is NULL. "
                "These rows are not automatically deleted by retention."
            )

        logger.info(
            f"[DRY RUN] Retention check for '{clean_table}': "
            f"{rows_matched} row(s) older than "
            f"{cutoff_at.to_iso8601_string()} would be deleted."
        )

        return {
            "table_name": clean_table,
            "timestamp_column": clean_column,
            "retention_days": retention_days,
            "enabled": policy["enabled"],
            "dry_run": True,
            "reference_time": reference_dt.to_iso8601_string(),
            "cutoff_at": cutoff_at.to_iso8601_string(),
            "batch_size": batch_size,
            "batches_executed": 0,
            "rows_matched": rows_matched,
            "rows_deleted": 0,
            "rows_affected": rows_matched,
            "null_timestamp_rows": null_timestamp_rows,
            "status": "success",
        }

    delete_sql = f"""
        WITH rows_to_delete AS (
            SELECT ctid
            FROM {table_sql}
            WHERE {column_sql} < :cutoff_at
            ORDER BY {column_sql}, ctid
            LIMIT :batch_size
        )
        DELETE FROM {table_sql} AS target
        USING rows_to_delete AS batch
        WHERE target.ctid = batch.ctid
    """

    total_deleted = 0
    batches_executed = 0

    for batch_number in range(1, max_batches + 1):
        row_count = execute_sql(
            delete_sql,
            {
                "cutoff_at": cutoff_at,
                "batch_size": batch_size,
            },
        )

        deleted_count = int(row_count or 0)

        if deleted_count < 0:
            raise RuntimeError(
                f"Unexpected negative row count while cleaning "
                f"'{clean_table}': {deleted_count}."
            )

        if deleted_count == 0:
            break

        total_deleted += deleted_count
        batches_executed += 1

        if batch_number == 1 or batch_number % 10 == 0:
            logger.info(
                f"Retention cleanup progress for '{clean_table}': "
                f"batches={batches_executed}, "
                f"rows_deleted={total_deleted}, "
                f"cutoff={cutoff_at.to_iso8601_string()}."
            )

        if deleted_count < batch_size:
            break
    else:
        raise RuntimeError(
            f"Retention cleanup for '{clean_table}' reached "
            f"max_batches={max_batches} before completion. "
            "Reduce cleanup range, increase operational capacity, "
            "or consider table partitioning."
        )

    logger.info(
        f"Retention cleanup completed for '{clean_table}': "
        f"{total_deleted} row(s) deleted in {batches_executed} batch(es), "
        f"cutoff={cutoff_at.to_iso8601_string()}."
    )

    return {
        "table_name": clean_table,
        "timestamp_column": clean_column,
        "retention_days": retention_days,
        "enabled": policy["enabled"],
        "dry_run": False,
        "reference_time": reference_dt.to_iso8601_string(),
        "cutoff_at": cutoff_at.to_iso8601_string(),
        "batch_size": batch_size,
        "batches_executed": batches_executed,
        "rows_matched": total_deleted,
        "rows_deleted": total_deleted,
        "rows_affected": total_deleted,
        "null_timestamp_rows": None,
        "status": "success",
    }


def run_retention_cleanup(
    dry_run: bool = False,
    enabled_only: bool = True,
    allow_disabled: bool = False,
    fail_on_any_error: bool = False,
    reference_time: Optional[Any] = None,
    max_batches_per_table: int = DEFAULT_MAX_BATCHES,
) -> Dict[str, Any]:
    """
    Execute retention cleanup across configured policies.

    Default behavior:
    - Continue processing remaining tables if one table fails.
    - Do not fail the whole run for one optional table error.
    - Raise RuntimeError only if every processed table fails.
    - If fail_on_any_error=True, raise when any table fails.

    This behavior is safer for MVP/dev because schema differences in one
    optional table should not block cleanup for all valid tables.
    """
    if not isinstance(dry_run, bool):
        raise ValueError("dry_run must be a boolean.")

    if not isinstance(enabled_only, bool):
        raise ValueError("enabled_only must be a boolean.")

    if not isinstance(allow_disabled, bool):
        raise ValueError("allow_disabled must be a boolean.")

    if not isinstance(fail_on_any_error, bool):
        raise ValueError("fail_on_any_error must be a boolean.")

    if (
        isinstance(max_batches_per_table, bool)
        or not isinstance(max_batches_per_table, int)
        or max_batches_per_table <= 0
    ):
        raise ValueError(
            "max_batches_per_table must be a positive integer."
        )

    if not dry_run and not enabled_only and not allow_disabled:
        raise ValueError(
            "Deleting disabled retention targets requires allow_disabled=True."
        )

    reference_dt = _normalize_reference_time(reference_time)
    policies = get_retention_policies()

    logger.info(
        f"Starting retention cleanup. "
        f"dry_run={dry_run}, "
        f"enabled_only={enabled_only}, "
        f"allow_disabled={allow_disabled}, "
        f"fail_on_any_error={fail_on_any_error}, "
        f"reference_time={reference_dt.to_iso8601_string()}."
    )

    results: List[Dict[str, Any]] = []

    successful_tables = 0
    failed_tables = 0
    skipped_tables = 0

    for policy in policies:
        table_name = str(policy.get("table_name", "<unknown>"))

        try:
            _validate_retention_policy(policy)

            if enabled_only and not policy["enabled"]:
                logger.info(
                    f"Skipping disabled retention policy for table '{table_name}'."
                )
                results.append(
                    {
                        "table_name": table_name,
                        "status": "skipped",
                        "reason": "policy_disabled",
                    }
                )
                skipped_tables += 1
                continue

            result = cleanup_table_by_retention(
                table_name=policy["table_name"],
                timestamp_column=policy["timestamp_column"],
                retention_days=policy["retention_days"],
                dry_run=dry_run,
                allow_disabled=allow_disabled,
                reference_time=reference_dt,
                max_batches=max_batches_per_table,
            )

            results.append(result)
            successful_tables += 1

        except Exception as exc:
            logger.exception(
                f"Retention cleanup failed for table '{table_name}'."
            )
            results.append(
                {
                    "table_name": table_name,
                    "status": "failed",
                    "error": str(exc),
                }
            )
            failed_tables += 1

    total_rows_matched = sum(
        int(result.get("rows_matched", 0) or 0)
        for result in results
        if result.get("status") == "success"
    )

    total_rows_deleted = sum(
        int(result.get("rows_deleted", 0) or 0)
        for result in results
        if result.get("status") == "success"
    )

    total_null_timestamp_rows = sum(
        int(result.get("null_timestamp_rows", 0) or 0)
        for result in results
        if result.get("status") == "success"
    )

    tables_processed = successful_tables + failed_tables

    summary = {
        "dry_run": dry_run,
        "reference_time": reference_dt.to_iso8601_string(),
        "policies_considered": len(policies),
        "tables_processed": tables_processed,
        "tables_skipped": skipped_tables,
        "successful_tables": successful_tables,
        "failed_tables": failed_tables,
        "total_rows_matched": total_rows_matched,
        "total_rows_deleted": total_rows_deleted,
        "total_null_timestamp_rows": total_null_timestamp_rows,
        "total_rows_affected": (
            total_rows_matched if dry_run else total_rows_deleted
        ),
        "results": results,
    }

    failed_names = [
        str(result.get("table_name", "<unknown>"))
        for result in results
        if result.get("status") == "failed"
    ]

    if failed_tables > 0:
        logger.error(
            f"Retention cleanup completed with table-level failures. "
            f"successful_tables={successful_tables}, "
            f"failed_tables={failed_tables}, "
            f"skipped_tables={skipped_tables}, "
            f"failed_targets={failed_names}."
        )

    if tables_processed == 0:
        raise RuntimeError(
            "Retention cleanup did not process any table. "
            "Check enabled_only and RETENTION_POLICIES configuration."
        )

    if successful_tables == 0 and failed_tables > 0:
        raise RuntimeError(
            "All retention cleanup operations failed: "
            + ", ".join(failed_names)
        )

    if failed_tables > 0 and fail_on_any_error:
        raise RuntimeError(
            "Retention cleanup failed for: "
            + ", ".join(failed_names)
        )

    logger.info(
        f"Retention cleanup finished. "
        f"dry_run={dry_run}, "
        f"processed={tables_processed}, "
        f"successful={successful_tables}, "
        f"failed={failed_tables}, "
        f"skipped={skipped_tables}, "
        f"rows_affected={summary['total_rows_affected']}."
    )

    return summary