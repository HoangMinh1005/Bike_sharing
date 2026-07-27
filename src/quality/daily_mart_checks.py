import pendulum

from src.common.db import fetch_one
from src.common.logger import get_logger
from src.quality.metadata_checks import write_dq_result

logger = get_logger(__name__)


def run_daily_mart_dq_checks(
    run_id: str,
    batch_id: str,
    target_date: str,
) -> None:
    """
    Run data quality checks for daily mart tables for the target date.

    Tables checked:
    - mart.daily_station_summary
    - mart.daily_region_summary
    - mart.station_demand_ranking
    - mart.daily_system_summary

    Critical checks raise ValueError and fail the pipeline.
    Warning checks are written to etl_metadata.dq_results but do not fail the pipeline.

    Note:
        DQ checks use target_date instead of batch_id because daily mart tables
        are keyed by business grain:
        - summary_date + station_id
        - summary_date + region_id
        - ranking_date + station_id
        - summary_date
    """
    try:
        parsed_date = pendulum.parse(str(target_date)).to_date_string()
    except Exception as e:
        raise ValueError(
            f"Invalid target_date format for DQ checks: "
            f"target_date={target_date}, error={e}"
        ) from e

    logger.info(
        f"Running daily mart data quality checks. "
        f"run_id={run_id}, batch_id={batch_id}, target_date={parsed_date}"
    )

    params = {
        "target_date": parsed_date,
    }

    checks = [
        # ==================================================
        # 1. mart.daily_station_summary CHECKS
        # ==================================================
        {
            "table": "mart.daily_station_summary",
            "name": "daily_station_summary_not_empty",
            "sql": """
                SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END AS failed_count
                FROM mart.daily_station_summary
                WHERE summary_date = CAST(:target_date AS DATE)
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: mart.daily_station_summary is empty."
            ),
        },
        {
            "table": "mart.daily_station_summary",
            "name": "daily_station_summary_station_id_not_null_or_empty",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_station_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND (
                      station_id IS NULL
                      OR TRIM(CAST(station_id AS TEXT)) = ''
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} station summary record(s) "
                "with NULL or empty station_id."
            ),
        },
        {
            "table": "mart.daily_station_summary",
            "name": "daily_station_summary_active_hour_count_positive",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_station_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND (
                      active_hour_count IS NULL
                      OR active_hour_count <= 0
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} station summary record(s) "
                "with active_hour_count <= 0 or NULL."
            ),
        },
        {
            "table": "mart.daily_station_summary",
            "name": "daily_station_summary_total_observation_count_positive",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_station_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND (
                      total_observation_count IS NULL
                      OR total_observation_count <= 0
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} station summary record(s) "
                "with total_observation_count <= 0 or NULL."
            ),
        },
        {
            "table": "mart.daily_station_summary",
            "name": "daily_station_summary_core_metrics_valid",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_station_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND (
                      avg_bikes_available IS NULL
                      OR avg_bikes_available < 0

                      OR avg_docks_available IS NULL
                      OR avg_docks_available < 0

                      OR avg_bikes_disabled IS NULL
                      OR avg_bikes_disabled < 0

                      OR avg_docks_disabled IS NULL
                      OR avg_docks_disabled < 0

                      OR min_bikes_available IS NULL
                      OR min_bikes_available < 0

                      OR max_bikes_available IS NULL
                      OR max_bikes_available < 0

                      OR min_bikes_available > max_bikes_available

                      OR empty_hour_count IS NULL
                      OR empty_hour_count < 0
                      OR empty_hour_count > active_hour_count

                      OR full_hour_count IS NULL
                      OR full_hour_count < 0
                      OR full_hour_count > active_hour_count

                      OR empty_observation_count IS NULL
                      OR empty_observation_count < 0
                      OR empty_observation_count > total_observation_count

                      OR full_observation_count IS NULL
                      OR full_observation_count < 0
                      OR full_observation_count > total_observation_count

                      OR low_availability_hour_count IS NULL
                      OR low_availability_hour_count < 0
                      OR low_availability_hour_count > active_hour_count

                      OR high_demand_hour_count IS NULL
                      OR high_demand_hour_count < 0
                      OR high_demand_hour_count > active_hour_count
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} station summary record(s) "
                "with invalid core metrics."
            ),
        },
        {
            "table": "mart.daily_station_summary",
            "name": "daily_station_summary_valid_availability_rate",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_station_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND avg_availability_rate IS NOT NULL
                  AND (
                      avg_availability_rate < 0
                      OR avg_availability_rate > 1
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} station summary record(s) "
                "with avg_availability_rate outside [0, 1]."
            ),
        },
        {
            "table": "mart.daily_station_summary",
            "name": "daily_station_summary_valid_dock_utilization_rate",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_station_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND avg_dock_utilization_rate IS NOT NULL
                  AND (
                      avg_dock_utilization_rate < 0
                      OR avg_dock_utilization_rate > 1
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} station summary record(s) "
                "with avg_dock_utilization_rate outside [0, 1]."
            ),
        },
        {
            "table": "mart.daily_station_summary",
            "name": "daily_station_summary_unique_station_date",
            "sql": """
                SELECT COALESCE(SUM(duplicate_count - 1), 0) AS failed_count
                FROM (
                    SELECT
                        summary_date,
                        station_id,
                        COUNT(*) AS duplicate_count
                    FROM mart.daily_station_summary
                    WHERE summary_date = CAST(:target_date AS DATE)
                    GROUP BY
                        summary_date,
                        station_id
                    HAVING COUNT(*) > 1
                ) dup
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} duplicate station summary "
                "record(s) by summary_date + station_id."
            ),
        },
        {
            "table": "mart.daily_station_summary",
            "name": "daily_station_summary_missing_station_metadata",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_station_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND station_name IS NULL
            """,
            "severity": "WARNING",
            "msg_template": (
                "Date {target_date}: Found {count} station summary record(s) "
                "missing station_name."
            ),
        },
        {
            "table": "mart.daily_station_summary",
            "name": "daily_station_summary_missing_region_metadata",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_station_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND region_name IS NULL
            """,
            "severity": "WARNING",
            "msg_template": (
                "Date {target_date}: Found {count} station summary record(s) "
                "missing region_name."
            ),
        },
        {
            "table": "mart.daily_station_summary",
            "name": "daily_station_summary_missing_weather",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_station_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND (
                      avg_temperature IS NULL
                      OR avg_wind_speed IS NULL
                      OR total_precipitation IS NULL
                  )
            """,
            "severity": "WARNING",
            "msg_template": (
                "Date {target_date}: Found {count} station summary record(s) "
                "missing weather enrichment."
            ),
        },
        {
            "table": "mart.daily_station_summary",
            "name": "daily_station_summary_missing_calendar",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_station_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND (
                      is_weekend IS NULL
                      OR is_holiday IS NULL
                  )
            """,
            "severity": "WARNING",
            "msg_template": (
                "Date {target_date}: Found {count} station summary record(s) "
                "missing calendar enrichment."
            ),
        },
        {
            "table": "mart.daily_station_summary",
            "name": "daily_station_summary_missing_holiday_name",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_station_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND is_holiday = TRUE
                  AND (
                      holiday_name IS NULL
                      OR TRIM(CAST(holiday_name AS TEXT)) = ''
                  )
            """,
            "severity": "WARNING",
            "msg_template": (
                "Date {target_date}: Found {count} station summary record(s) "
                "where is_holiday is true but holiday_name is missing."
            ),
        },

        # ==================================================
        # 2. mart.daily_region_summary CHECKS
        # ==================================================
        {
            "table": "mart.daily_region_summary",
            "name": "daily_region_summary_not_empty",
            "sql": """
                SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END AS failed_count
                FROM mart.daily_region_summary
                WHERE summary_date = CAST(:target_date AS DATE)
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: mart.daily_region_summary is empty."
            ),
        },
        {
            "table": "mart.daily_region_summary",
            "name": "daily_region_summary_region_id_not_null_or_empty",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_region_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND (
                      region_id IS NULL
                      OR TRIM(CAST(region_id AS TEXT)) = ''
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} region summary record(s) "
                "with NULL or empty region_id."
            ),
        },
        {
            "table": "mart.daily_region_summary",
            "name": "daily_region_summary_station_count_valid",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_region_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND (
                      station_count IS NULL
                      OR station_count <= 0
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} region summary record(s) "
                "with invalid station_count."
            ),
        },
        {
            "table": "mart.daily_region_summary",
            "name": "daily_region_summary_active_station_count_valid",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_region_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND (
                      active_station_count IS NULL
                      OR active_station_count < 0
                      OR station_count IS NULL
                      OR active_station_count > station_count
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} region summary record(s) "
                "with invalid active_station_count."
            ),
        },
        {
            "table": "mart.daily_region_summary",
            "name": "daily_region_summary_core_metrics_valid",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_region_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND (
                      total_observation_count IS NULL
                      OR total_observation_count <= 0

                      OR avg_bikes_available IS NULL
                      OR avg_bikes_available < 0

                      OR avg_docks_available IS NULL
                      OR avg_docks_available < 0

                      OR total_bikes_available IS NULL
                      OR total_bikes_available < 0

                      OR total_docks_available IS NULL
                      OR total_docks_available < 0

                      OR empty_station_count IS NULL
                      OR empty_station_count < 0
                      OR empty_station_count > station_count

                      OR full_station_count IS NULL
                      OR full_station_count < 0
                      OR full_station_count > station_count

                      OR low_availability_station_count IS NULL
                      OR low_availability_station_count < 0
                      OR low_availability_station_count > station_count

                      OR high_demand_station_count IS NULL
                      OR high_demand_station_count < 0
                      OR high_demand_station_count > station_count
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} region summary record(s) "
                "with invalid core metrics."
            ),
        },
        {
            "table": "mart.daily_region_summary",
            "name": "daily_region_summary_valid_availability_rate",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_region_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND avg_availability_rate IS NOT NULL
                  AND (
                      avg_availability_rate < 0
                      OR avg_availability_rate > 1
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} region summary record(s) "
                "with avg_availability_rate outside [0, 1]."
            ),
        },
        {
            "table": "mart.daily_region_summary",
            "name": "daily_region_summary_valid_dock_utilization_rate",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_region_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND avg_dock_utilization_rate IS NOT NULL
                  AND (
                      avg_dock_utilization_rate < 0
                      OR avg_dock_utilization_rate > 1
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} region summary record(s) "
                "with avg_dock_utilization_rate outside [0, 1]."
            ),
        },
        {
            "table": "mart.daily_region_summary",
            "name": "daily_region_summary_unique_region_date",
            "sql": """
                SELECT COALESCE(SUM(duplicate_count - 1), 0) AS failed_count
                FROM (
                    SELECT
                        summary_date,
                        region_id,
                        COUNT(*) AS duplicate_count
                    FROM mart.daily_region_summary
                    WHERE summary_date = CAST(:target_date AS DATE)
                    GROUP BY
                        summary_date,
                        region_id
                    HAVING COUNT(*) > 1
                ) dup
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} duplicate region summary "
                "record(s) by summary_date + region_id."
            ),
        },
        {
            "table": "mart.daily_region_summary",
            "name": "daily_region_summary_missing_region_name",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_region_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND region_name IS NULL
            """,
            "severity": "WARNING",
            "msg_template": (
                "Date {target_date}: Found {count} region summary record(s) "
                "missing region_name."
            ),
        },
        {
            "table": "mart.daily_region_summary",
            "name": "daily_region_summary_missing_weather",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_region_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND (
                      avg_temperature IS NULL
                      OR avg_wind_speed IS NULL
                      OR total_precipitation IS NULL
                  )
            """,
            "severity": "WARNING",
            "msg_template": (
                "Date {target_date}: Found {count} region summary record(s) "
                "missing weather enrichment."
            ),
        },
        {
            "table": "mart.daily_region_summary",
            "name": "daily_region_summary_missing_calendar",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_region_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND (
                      is_weekend IS NULL
                      OR is_holiday IS NULL
                  )
            """,
            "severity": "WARNING",
            "msg_template": (
                "Date {target_date}: Found {count} region summary record(s) "
                "missing calendar enrichment."
            ),
        },
        {
            "table": "mart.daily_region_summary",
            "name": "daily_region_summary_missing_holiday_name",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_region_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND is_holiday = TRUE
                  AND (
                      holiday_name IS NULL
                      OR TRIM(CAST(holiday_name AS TEXT)) = ''
                  )
            """,
            "severity": "WARNING",
            "msg_template": (
                "Date {target_date}: Found {count} region summary record(s) "
                "where is_holiday is true but holiday_name is missing."
            ),
        },

        # ==================================================
        # 3. mart.station_demand_ranking CHECKS
        # ==================================================
        {
            "table": "mart.station_demand_ranking",
            "name": "station_demand_ranking_not_empty",
            "sql": """
                SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END AS failed_count
                FROM mart.station_demand_ranking
                WHERE ranking_date = CAST(:target_date AS DATE)
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: mart.station_demand_ranking is empty."
            ),
        },
        {
            "table": "mart.station_demand_ranking",
            "name": "station_demand_ranking_station_id_not_null_or_empty",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.station_demand_ranking
                WHERE ranking_date = CAST(:target_date AS DATE)
                  AND (
                      station_id IS NULL
                      OR TRIM(CAST(station_id AS TEXT)) = ''
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} station demand ranking "
                "record(s) with NULL or empty station_id."
            ),
        },
        {
            "table": "mart.station_demand_ranking",
            "name": "station_demand_ranking_score_valid",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.station_demand_ranking
                WHERE ranking_date = CAST(:target_date AS DATE)
                  AND (
                      demand_score IS NULL
                      OR demand_score < 0
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} station demand ranking "
                "record(s) with invalid demand_score."
            ),
        },
        {
            "table": "mart.station_demand_ranking",
            "name": "station_demand_ranking_rank_valid",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.station_demand_ranking
                WHERE ranking_date = CAST(:target_date AS DATE)
                  AND (
                      demand_rank IS NULL
                      OR demand_rank <= 0
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} station demand ranking "
                "record(s) with invalid demand_rank."
            ),
        },
        {
            "table": "mart.station_demand_ranking",
            "name": "station_demand_ranking_category_valid",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.station_demand_ranking
                WHERE ranking_date = CAST(:target_date AS DATE)
                  AND (
                      demand_category IS NULL
                      OR demand_category NOT IN ('HIGH', 'MEDIUM', 'LOW')
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} station demand ranking "
                "record(s) with invalid demand_category."
            ),
        },
        {
            "table": "mart.station_demand_ranking",
            "name": "station_demand_ranking_unique_station_date",
            "sql": """
                SELECT COALESCE(SUM(duplicate_count - 1), 0) AS failed_count
                FROM (
                    SELECT
                        ranking_date,
                        station_id,
                        COUNT(*) AS duplicate_count
                    FROM mart.station_demand_ranking
                    WHERE ranking_date = CAST(:target_date AS DATE)
                    GROUP BY
                        ranking_date,
                        station_id
                    HAVING COUNT(*) > 1
                ) dup
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} duplicate station ranking "
                "record(s) by ranking_date + station_id."
            ),
        },
        {
            "table": "mart.station_demand_ranking",
            "name": "station_demand_ranking_row_count_matches_daily_station_summary",
            "sql": """
                SELECT
                    CASE
                        WHEN (
                            SELECT COUNT(*)
                            FROM mart.station_demand_ranking
                            WHERE ranking_date = CAST(:target_date AS DATE)
                        ) != (
                            SELECT COUNT(*)
                            FROM mart.daily_station_summary
                            WHERE summary_date = CAST(:target_date AS DATE)
                        )
                        THEN 1
                        ELSE 0
                    END AS failed_count
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: station_demand_ranking row count does not "
                "match daily_station_summary row count."
            ),
        },

        # ==================================================
        # 4. mart.daily_system_summary CHECKS
        # ==================================================
        {
            "table": "mart.daily_system_summary",
            "name": "daily_system_summary_not_empty",
            "sql": """
                SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END AS failed_count
                FROM mart.daily_system_summary
                WHERE summary_date = CAST(:target_date AS DATE)
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: mart.daily_system_summary is empty."
            ),
        },
        {
            "table": "mart.daily_system_summary",
            "name": "daily_system_summary_unique_date",
            "sql": """
                SELECT COALESCE(SUM(duplicate_count - 1), 0) AS failed_count
                FROM (
                    SELECT
                        summary_date,
                        COUNT(*) AS duplicate_count
                    FROM mart.daily_system_summary
                    WHERE summary_date = CAST(:target_date AS DATE)
                    GROUP BY
                        summary_date
                    HAVING COUNT(*) > 1
                ) dup
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} duplicate daily system "
                "summary record(s)."
            ),
        },
        {
            "table": "mart.daily_system_summary",
            "name": "daily_system_summary_station_count_valid",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_system_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND (
                      station_count IS NULL
                      OR station_count <= 0
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} system summary record(s) "
                "with invalid station_count."
            ),
        },
        {
            "table": "mart.daily_system_summary",
            "name": "daily_system_summary_active_station_count_valid",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_system_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND (
                      active_station_count IS NULL
                      OR active_station_count < 0
                      OR station_count IS NULL
                      OR active_station_count > station_count
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} system summary record(s) "
                "with invalid active_station_count."
            ),
        },
        {
            "table": "mart.daily_system_summary",
            "name": "daily_system_summary_region_count_valid",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_system_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND (
                      region_count IS NULL
                      OR region_count < 0
                      OR region_count > station_count
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} system summary record(s) "
                "with invalid region_count."
            ),
        },
        {
            "table": "mart.daily_system_summary",
            "name": "daily_system_summary_core_metrics_valid",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_system_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND (
                      total_observation_count IS NULL
                      OR total_observation_count <= 0

                      OR avg_bikes_available IS NULL
                      OR avg_bikes_available < 0

                      OR avg_docks_available IS NULL
                      OR avg_docks_available < 0

                      OR total_bikes_available IS NULL
                      OR total_bikes_available < 0

                      OR total_docks_available IS NULL
                      OR total_docks_available < 0

                      OR empty_station_count IS NULL
                      OR empty_station_count < 0
                      OR empty_station_count > station_count

                      OR full_station_count IS NULL
                      OR full_station_count < 0
                      OR full_station_count > station_count

                      OR low_availability_station_count IS NULL
                      OR low_availability_station_count < 0
                      OR low_availability_station_count > station_count

                      OR high_demand_station_count IS NULL
                      OR high_demand_station_count < 0
                      OR high_demand_station_count > station_count
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} system summary record(s) "
                "with invalid core metrics."
            ),
        },
        {
            "table": "mart.daily_system_summary",
            "name": "daily_system_summary_valid_availability_rate",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_system_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND avg_availability_rate IS NOT NULL
                  AND (
                      avg_availability_rate < 0
                      OR avg_availability_rate > 1
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} system summary record(s) "
                "with avg_availability_rate outside [0, 1]."
            ),
        },
        {
            "table": "mart.daily_system_summary",
            "name": "daily_system_summary_valid_dock_utilization_rate",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_system_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND avg_dock_utilization_rate IS NOT NULL
                  AND (
                      avg_dock_utilization_rate < 0
                      OR avg_dock_utilization_rate > 1
                  )
            """,
            "severity": "CRITICAL",
            "msg_template": (
                "Date {target_date}: Found {count} system summary record(s) "
                "with avg_dock_utilization_rate outside [0, 1]."
            ),
        },
        {
            "table": "mart.daily_system_summary",
            "name": "daily_system_summary_missing_weather",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_system_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND (
                      avg_temperature IS NULL
                      OR avg_wind_speed IS NULL
                      OR total_precipitation IS NULL
                  )
            """,
            "severity": "WARNING",
            "msg_template": (
                "Date {target_date}: Found {count} system summary record(s) "
                "missing weather enrichment."
            ),
        },
        {
            "table": "mart.daily_system_summary",
            "name": "daily_system_summary_missing_calendar",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_system_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND (
                      is_weekend IS NULL
                      OR is_holiday IS NULL
                  )
            """,
            "severity": "WARNING",
            "msg_template": (
                "Date {target_date}: Found {count} system summary record(s) "
                "missing calendar enrichment."
            ),
        },
        {
            "table": "mart.daily_system_summary",
            "name": "daily_system_summary_missing_holiday_name",
            "sql": """
                SELECT COUNT(*) AS failed_count
                FROM mart.daily_system_summary
                WHERE summary_date = CAST(:target_date AS DATE)
                  AND is_holiday = TRUE
                  AND (
                      holiday_name IS NULL
                      OR TRIM(CAST(holiday_name AS TEXT)) = ''
                  )
            """,
            "severity": "WARNING",
            "msg_template": (
                "Date {target_date}: Found {count} system summary record(s) "
                "where is_holiday is true but holiday_name is missing."
            ),
        },
    ]

    critical_failures = []

    for check in checks:
        try:
            result = fetch_one(check["sql"], params)
            failed_count = int(result["failed_count"] or 0) if result else 0

            if failed_count > 0:
                message = check["msg_template"].format(
                    target_date=parsed_date,
                    count=failed_count,
                )
                status = "failed"

                if check["severity"] == "CRITICAL":
                    logger.error(
                        f"DQ Check FAILED: {check['name']} "
                        f"on {check['table']} - {message}"
                    )
                    critical_failures.append(f"{check['name']}: {message}")
                else:
                    logger.warning(
                        f"DQ Check WARNING: {check['name']} "
                        f"on {check['table']} - {message}"
                    )
            else:
                status = "passed"
                message = (
                    f"Date {parsed_date}: All records passed check."
                )

                logger.info(
                    f"DQ Check PASSED: {check['name']} "
                    f"on {check['table']}"
                )

            write_dq_result(
                run_id=run_id,
                table_name=check["table"],
                check_name=check["name"],
                status=status,
                failed_count=failed_count,
                severity=check["severity"],
                message=message,
            )

        except Exception as e:
            error_message = (
                f"Execution error while running DQ check "
                f"'{check['name']}' on {check['table']}: {e}"
            )
            logger.error(error_message)

            write_dq_result(
                run_id=run_id,
                table_name=check["table"],
                check_name=check["name"],
                status="failed",
                failed_count=1,
                severity=check["severity"],
                message=error_message,
            )

            if check["severity"] == "CRITICAL":
                critical_failures.append(
                    f"{check['name']} execution error: {e}"
                )

    if critical_failures:
        error_message = "; ".join(critical_failures)

        logger.error(
            f"Critical daily mart DQ check failures: {error_message}"
        )

        raise ValueError(
            f"Critical daily mart DQ checks failed: {error_message}"
        )

    logger.info(
        f"All daily mart DQ checks executed successfully for date {parsed_date}."
    )