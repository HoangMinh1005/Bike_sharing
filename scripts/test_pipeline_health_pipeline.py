import uuid
import pendulum

from src.common.db import execute_sql, fetch_all, fetch_one
from src.common.logger import get_logger
from src.metadata.pipeline_run_tracker import (
    start_pipeline_run,
    finish_pipeline_run_success,
    finish_pipeline_run_failed,
)
from src.metadata.watermark_manager import update_watermark
from src.monitoring.pipeline_health_builder import (
    build_pipeline_health_summary,
    get_monitored_pipelines,
)
from src.quality.pipeline_health_checks import run_pipeline_health_dq_checks

logger = get_logger(__name__)


def run_pipeline_health_smoke_test():
    """
    Execute end-to-end smoke test for pipeline health & DQ summary monitoring.
    """
    dag_id = "test_pipeline_health_smoke"
    run_id = f"manual-pipeline-health-smoke-{uuid.uuid4()}"
    batch_id = run_id
    checked_at = pendulum.now("UTC").to_iso8601_string()

    monitored = get_monitored_pipelines()
    total_monitored = len(monitored)

    logger.info(f"Starting pipeline health smoke test: run_id={run_id}")

    try:
        # 1. Start pipeline run tracking
        start_pipeline_run(run_id=run_id, dag_id=dag_id)

        # 2. Cleanup existing records for this health_run_id
        execute_sql(
            """
            DELETE FROM etl_metadata.pipeline_health_summary
            WHERE health_run_id = :health_run_id
            """,
            {"health_run_id": run_id},
        )

        # 3. Build pipeline health summary
        loaded = build_pipeline_health_summary(
            health_run_id=run_id,
            batch_id=batch_id,
            checked_at=checked_at,
        )

        # 4. Run DQ checks
        run_pipeline_health_dq_checks(run_id=run_id, batch_id=batch_id)

        # 5. Update smoke test watermark
        update_watermark("pipeline_health_smoke_test", checked_at)

        # 6. Complete pipeline tracking
        finish_pipeline_run_success(
            run_id=run_id,
            records_extracted=total_monitored,
            records_loaded=loaded,
            records_rejected=0,
        )

        # 7. Query health summary records and generate status summary
        summary_rows = fetch_all(
            """
            SELECT monitored_dag_id, pipeline_type, latest_run_status,
                   freshness_lag_minutes, dq_total_checks, dq_warning_checks,
                   dq_critical_failed_checks, health_status, health_message
            FROM etl_metadata.pipeline_health_summary
            WHERE health_run_id = :health_run_id
            ORDER BY monitored_dag_id
            """,
            {"health_run_id": run_id},
        )

        status_counts = {
            "HEALTHY": 0,
            "WARNING": 0,
            "FAILED": 0,
            "STALE": 0,
            "UNKNOWN": 0,
        }

        for row in summary_rows:
            st = row.get("health_status", "UNKNOWN")
            if st in status_counts:
                status_counts[st] += 1
            else:
                status_counts["UNKNOWN"] += 1

        logger.info("==========================================================")
        logger.info("Pipeline Health Monitoring Smoke Test Summary:")
        logger.info(f"  - Run ID: {run_id}")
        logger.info(f"  - Checked At: {checked_at}")
        logger.info(f"  - Total Monitored Pipelines Evaluated: {loaded}")
        logger.info(f"  - HEALTHY Pipelines: {status_counts['HEALTHY']}")
        logger.info(f"  - WARNING Pipelines: {status_counts['WARNING']}")
        logger.info(f"  - FAILED Pipelines:  {status_counts['FAILED']}")
        logger.info(f"  - STALE Pipelines:   {status_counts['STALE']}")
        logger.info(f"  - UNKNOWN Pipelines: {status_counts['UNKNOWN']}")
        logger.info("----------------------------------------------------------")
        for row in summary_rows:
            logger.info(
                f"  * [{row['health_status']:<7}] DAG: {row['monitored_dag_id']:<30} | "
                f"LatestStatus: {str(row['latest_run_status']):<8} | "
                f"Lag: {str(row['freshness_lag_minutes'])}m | "
                f"Msg: {row['health_message']}"
            )
        logger.info("==========================================================")
        logger.info("Pipeline health monitoring smoke test completed successfully.")

    except Exception as e:
        logger.error(f"Pipeline health smoke test failed: {e}")
        finish_pipeline_run_failed(run_id=run_id, error_message=str(e))
        raise


if __name__ == "__main__":
    run_pipeline_health_smoke_test()
