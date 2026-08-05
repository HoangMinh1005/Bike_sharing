import pytest

from src.cleanup.retention_manager import run_retention_cleanup
from src.common.logger import get_logger

logger = get_logger(__name__)


def test_retention_cleanup_dry_run_smoke():
    """
    Smoke test for retention cleanup manager in dry_run mode.
    """
    summary = run_retention_cleanup(
        dry_run=True,
        enabled_only=True,
        fail_on_any_error=False,
    )

    print(f"\nRetention Cleanup Dry-Run Summary: {summary}")

    assert summary["dry_run"] is True
    assert summary["tables_processed"] > 0
    assert summary["total_rows_affected"] >= 0
    assert isinstance(summary["results"], list)

    failed_tables = summary.get("failed_tables", 0)
    successful_tables = summary.get("successful_tables", 0)

    if failed_tables > 0:
        failed_names = [r["table_name"] for r in summary["results"] if r.get("status") == "failed"]
        print(f"WARNING: Retention cleanup dry-run encountered errors on {failed_tables} table(s): {failed_names}")

    assert successful_tables > 0, "Retention cleanup dry-run failed on all target tables."

    print("\nRETENTION DRY-RUN SMOKE TEST PASSED")
