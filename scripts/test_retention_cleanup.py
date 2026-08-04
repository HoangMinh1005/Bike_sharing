import sys
import pendulum

from src.cleanup.retention_manager import run_retention_cleanup
from src.common.logger import get_logger
from src.metadata.pipeline_run_tracker import (
    start_pipeline_run,
    finish_pipeline_run_success,
    finish_pipeline_run_failed,
)

logger = get_logger(__name__)


def run_retention_cleanup_smoke_test():
    """
    Smoke test for retention cleanup manager in dry_run mode.
    """
    logger.info("==========================================================")
    logger.info("Starting Retention Cleanup Smoke Test (DRY RUN)")
    logger.info("==========================================================")

    run_id = f"smoke_test_retention_{pendulum.now('UTC').format('YYYYMMDD_HHmmss')}"
    dag_id = "retention_cleanup_smoke_test"

    start_pipeline_run(run_id=run_id, dag_id=dag_id)

    try:
        summary = run_retention_cleanup(dry_run=True, enabled_only=True)

        logger.info(f"Retention Cleanup summary (DRY RUN): {summary}")

        assert summary["dry_run"] is True
        assert summary["tables_processed"] > 0
        assert summary["total_rows_affected"] >= 0
        assert summary["successful_tables"] > 0
        assert summary["failed_tables"] == 0

        finish_pipeline_run_success(
            run_id=run_id,
            records_extracted=summary["tables_processed"],
            records_loaded=0,
            records_rejected=0,
        )

        logger.info("==========================================================")
        logger.info("Retention Cleanup Smoke Test PASSED SUCCESSFULLY!")
        logger.info("==========================================================")

    except Exception as e:
        logger.error(f"Retention Cleanup Smoke Test FAILED: {e}")
        finish_pipeline_run_failed(run_id=run_id, error_message=str(e))
        sys.exit(1)


if __name__ == "__main__":
    run_retention_cleanup_smoke_test()
