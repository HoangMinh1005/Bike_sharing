import pendulum

from src.common.db import execute_sql
from src.common.logger import get_logger

logger = get_logger(__name__)


def _validate_target_date(target_date: str) -> str:
    """
    Validate target daily mart build date string.

    Returns:
        Formatted date string: YYYY-MM-DD

    Raises:
        ValueError if target_date cannot be parsed.
    """
    try:
        parsed = pendulum.parse(str(target_date))
        return parsed.to_date_string()
    except Exception as e:
        raise ValueError(
            f"Invalid target_date format. "
            f"Provided target_date='{target_date}'. error={e}"
        ) from e


def build_daily_station_summary(
    target_date: str,
    batch_id: str,
    run_id: str,
) -> int:
    """
    Build mart.daily_station_summary for the target summary date.

    Grain:
        1 row / station_id / summary_date

    Source:
        mart.hourly_station_availability

    Weather metric design:
        Weather metrics are calculated from the hourly records available
        for each station. Therefore, two stations may have different
        avg_temperature / avg_wind_speed / total_precipitation if they have
        different hourly observation coverage.

        This is intentional for the MVP:
        weather metrics mean "weather observed during the hours where this
        station has available mart records", not "the absolute full-day
        weather average of the whole system".

    Returns:
        Number of rows inserted/upserted.
    """
    clean_date = _validate_target_date(target_date)

    logger.info(
        f"Building mart.daily_station_summary for target_date={clean_date}, "
        f"batch_id={batch_id}, run_id={run_id}"
    )

    sql = """
        INSERT INTO mart.daily_station_summary (
            summary_date,
            station_id,
            station_name,
            region_id,
            region_name,
            latitude,
            longitude,
            capacity,
            active_hour_count,
            total_observation_count,
            avg_bikes_available,
            avg_docks_available,
            avg_bikes_disabled,
            avg_docks_disabled,
            min_bikes_available,
            max_bikes_available,
            empty_hour_count,
            full_hour_count,
            empty_observation_count,
            full_observation_count,
            avg_availability_rate,
            avg_dock_utilization_rate,
            low_availability_hour_count,
            high_demand_hour_count,
            is_weekend,
            is_holiday,
            holiday_name,
            avg_temperature,
            total_precipitation,
            avg_wind_speed,
            batch_id,
            run_id,
            updated_at
        )
        SELECT
            CAST(:target_date AS DATE) AS summary_date,
            hsa.station_id,
            MAX(hsa.station_name) AS station_name,
            MAX(hsa.region_id) AS region_id,
            MAX(hsa.region_name) AS region_name,
            MAX(hsa.latitude) AS latitude,
            MAX(hsa.longitude) AS longitude,
            MAX(hsa.capacity) AS capacity,

            COUNT(hsa.hour_bucket) AS active_hour_count,
            SUM(hsa.observation_count) AS total_observation_count,

            AVG(hsa.avg_bikes_available) AS avg_bikes_available,
            AVG(hsa.avg_docks_available) AS avg_docks_available,
            AVG(hsa.avg_bikes_disabled) AS avg_bikes_disabled,
            AVG(hsa.avg_docks_disabled) AS avg_docks_disabled,

            MIN(hsa.min_bikes_available) AS min_bikes_available,
            MAX(hsa.max_bikes_available) AS max_bikes_available,

            COUNT(CASE WHEN hsa.avg_bikes_available = 0 THEN 1 END) AS empty_hour_count,
            COUNT(CASE WHEN hsa.avg_docks_available = 0 THEN 1 END) AS full_hour_count,
            SUM(hsa.empty_observation_count) AS empty_observation_count,
            SUM(hsa.full_observation_count) AS full_observation_count,

            CASE
                WHEN AVG(hsa.availability_rate) IS NULL THEN NULL
                ELSE LEAST(1.0, GREATEST(0.0, AVG(hsa.availability_rate)))
            END AS avg_availability_rate,

            CASE
                WHEN AVG(hsa.dock_utilization_rate) IS NULL THEN NULL
                ELSE LEAST(1.0, GREATEST(0.0, AVG(hsa.dock_utilization_rate)))
            END AS avg_dock_utilization_rate,

            COUNT(CASE WHEN hsa.availability_rate < 0.2 THEN 1 END) AS low_availability_hour_count,

            COUNT(
                CASE
                    WHEN hsa.availability_rate < 0.2
                      OR hsa.avg_bikes_available <= 2
                    THEN 1
                END
            ) AS high_demand_hour_count,

            BOOL_OR(hsa.is_weekend) AS is_weekend,
            BOOL_OR(hsa.is_holiday) AS is_holiday,
            MAX(hsa.holiday_name) AS holiday_name,

            AVG(hsa.temperature) AS avg_temperature,
            SUM(hsa.precipitation) AS total_precipitation,
            AVG(hsa.wind_speed) AS avg_wind_speed,

            :batch_id AS batch_id,
            :run_id AS run_id,
            CURRENT_TIMESTAMP AS updated_at

        FROM mart.hourly_station_availability hsa
        WHERE hsa.hour_bucket >= CAST(:target_date AS DATE)
          AND hsa.hour_bucket < CAST(:target_date AS DATE) + INTERVAL '1 day'
        GROUP BY
            hsa.station_id

        ON CONFLICT (summary_date, station_id) DO UPDATE SET
            station_name = EXCLUDED.station_name,
            region_id = EXCLUDED.region_id,
            region_name = EXCLUDED.region_name,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            capacity = EXCLUDED.capacity,
            active_hour_count = EXCLUDED.active_hour_count,
            total_observation_count = EXCLUDED.total_observation_count,
            avg_bikes_available = EXCLUDED.avg_bikes_available,
            avg_docks_available = EXCLUDED.avg_docks_available,
            avg_bikes_disabled = EXCLUDED.avg_bikes_disabled,
            avg_docks_disabled = EXCLUDED.avg_docks_disabled,
            min_bikes_available = EXCLUDED.min_bikes_available,
            max_bikes_available = EXCLUDED.max_bikes_available,
            empty_hour_count = EXCLUDED.empty_hour_count,
            full_hour_count = EXCLUDED.full_hour_count,
            empty_observation_count = EXCLUDED.empty_observation_count,
            full_observation_count = EXCLUDED.full_observation_count,
            avg_availability_rate = EXCLUDED.avg_availability_rate,
            avg_dock_utilization_rate = EXCLUDED.avg_dock_utilization_rate,
            low_availability_hour_count = EXCLUDED.low_availability_hour_count,
            high_demand_hour_count = EXCLUDED.high_demand_hour_count,
            is_weekend = EXCLUDED.is_weekend,
            is_holiday = EXCLUDED.is_holiday,
            holiday_name = EXCLUDED.holiday_name,
            avg_temperature = EXCLUDED.avg_temperature,
            total_precipitation = EXCLUDED.total_precipitation,
            avg_wind_speed = EXCLUDED.avg_wind_speed,
            batch_id = EXCLUDED.batch_id,
            run_id = EXCLUDED.run_id,
            updated_at = CURRENT_TIMESTAMP
    """

    params = {
        "target_date": clean_date,
        "batch_id": batch_id,
        "run_id": run_id,
    }

    count = execute_sql(sql, params)

    logger.info(
        f"Built mart.daily_station_summary for target_date={clean_date}. "
        f"records_processed={count}"
    )

    return count


def build_daily_region_summary(
    target_date: str,
    batch_id: str,
    run_id: str,
) -> int:
    """
    Build mart.daily_region_summary for the target summary date.

    Grain:
        1 row / region_id / summary_date

    Source:
        mart.daily_station_summary

    Weather metric design:
        Region-level weather metrics are aggregated from station-level
        observed weather metrics.

        This means avg_temperature / avg_wind_speed can differ by region
        because each region can have different station/hour observation coverage.

        total_precipitation is calculated as AVG of station-level
        total_precipitation to avoid multiplying the same weather source by
        station_count.

    Returns:
        Number of rows inserted/upserted.
    """
    clean_date = _validate_target_date(target_date)

    logger.info(
        f"Building mart.daily_region_summary for target_date={clean_date}, "
        f"batch_id={batch_id}, run_id={run_id}"
    )

    sql = """
        INSERT INTO mart.daily_region_summary (
            summary_date,
            region_id,
            region_name,
            station_count,
            active_station_count,
            total_observation_count,
            avg_bikes_available,
            avg_docks_available,
            total_bikes_available,
            total_docks_available,
            avg_availability_rate,
            avg_dock_utilization_rate,
            empty_station_count,
            full_station_count,
            low_availability_station_count,
            high_demand_station_count,
            is_weekend,
            is_holiday,
            holiday_name,
            avg_temperature,
            total_precipitation,
            avg_wind_speed,
            batch_id,
            run_id,
            updated_at
        )
        SELECT
            dss.summary_date,
            COALESCE(dss.region_id, 'UNKNOWN') AS region_id,
            MAX(dss.region_name) AS region_name,

            COUNT(DISTINCT dss.station_id) AS station_count,
            COUNT(
                DISTINCT CASE
                    WHEN dss.active_hour_count > 0 THEN dss.station_id
                END
            ) AS active_station_count,

            SUM(dss.total_observation_count) AS total_observation_count,

            AVG(dss.avg_bikes_available) AS avg_bikes_available,
            AVG(dss.avg_docks_available) AS avg_docks_available,

            SUM(dss.avg_bikes_available) AS total_bikes_available,
            SUM(dss.avg_docks_available) AS total_docks_available,

            CASE
                WHEN AVG(dss.avg_availability_rate) IS NULL THEN NULL
                ELSE LEAST(1.0, GREATEST(0.0, AVG(dss.avg_availability_rate)))
            END AS avg_availability_rate,

            CASE
                WHEN AVG(dss.avg_dock_utilization_rate) IS NULL THEN NULL
                ELSE LEAST(1.0, GREATEST(0.0, AVG(dss.avg_dock_utilization_rate)))
            END AS avg_dock_utilization_rate,

            COUNT(CASE WHEN dss.avg_bikes_available = 0 THEN 1 END) AS empty_station_count,
            COUNT(CASE WHEN dss.avg_docks_available = 0 THEN 1 END) AS full_station_count,
            COUNT(CASE WHEN dss.avg_availability_rate < 0.2 THEN 1 END) AS low_availability_station_count,
            COUNT(CASE WHEN dss.high_demand_hour_count > 0 THEN 1 END) AS high_demand_station_count,

            BOOL_OR(dss.is_weekend) AS is_weekend,
            BOOL_OR(dss.is_holiday) AS is_holiday,
            MAX(dss.holiday_name) AS holiday_name,

            AVG(dss.avg_temperature) AS avg_temperature,
            AVG(dss.total_precipitation) AS total_precipitation,
            AVG(dss.avg_wind_speed) AS avg_wind_speed,

            :batch_id AS batch_id,
            :run_id AS run_id,
            CURRENT_TIMESTAMP AS updated_at

        FROM mart.daily_station_summary dss
        WHERE dss.summary_date = CAST(:target_date AS DATE)
        GROUP BY
            dss.summary_date,
            COALESCE(dss.region_id, 'UNKNOWN')

        ON CONFLICT (summary_date, region_id) DO UPDATE SET
            region_name = EXCLUDED.region_name,
            station_count = EXCLUDED.station_count,
            active_station_count = EXCLUDED.active_station_count,
            total_observation_count = EXCLUDED.total_observation_count,
            avg_bikes_available = EXCLUDED.avg_bikes_available,
            avg_docks_available = EXCLUDED.avg_docks_available,
            total_bikes_available = EXCLUDED.total_bikes_available,
            total_docks_available = EXCLUDED.total_docks_available,
            avg_availability_rate = EXCLUDED.avg_availability_rate,
            avg_dock_utilization_rate = EXCLUDED.avg_dock_utilization_rate,
            empty_station_count = EXCLUDED.empty_station_count,
            full_station_count = EXCLUDED.full_station_count,
            low_availability_station_count = EXCLUDED.low_availability_station_count,
            high_demand_station_count = EXCLUDED.high_demand_station_count,
            is_weekend = EXCLUDED.is_weekend,
            is_holiday = EXCLUDED.is_holiday,
            holiday_name = EXCLUDED.holiday_name,
            avg_temperature = EXCLUDED.avg_temperature,
            total_precipitation = EXCLUDED.total_precipitation,
            avg_wind_speed = EXCLUDED.avg_wind_speed,
            batch_id = EXCLUDED.batch_id,
            run_id = EXCLUDED.run_id,
            updated_at = CURRENT_TIMESTAMP
    """

    params = {
        "target_date": clean_date,
        "batch_id": batch_id,
        "run_id": run_id,
    }

    count = execute_sql(sql, params)

    logger.info(
        f"Built mart.daily_region_summary for target_date={clean_date}. "
        f"records_processed={count}"
    )

    return count


def build_station_demand_ranking(
    target_date: str,
    batch_id: str,
    run_id: str,
) -> int:
    """
    Build mart.station_demand_ranking for the target ranking date.

    Grain:
        1 row / station_id / ranking_date

    Source:
        mart.daily_station_summary

    Scoring formula:
        demand_score =
            COALESCE(low_availability_hour_count, 0) * 3
          + COALESCE(empty_hour_count, 0) * 5
          + COALESCE(full_hour_count, 0) * 1
          + (1.0 - COALESCE(avg_availability_rate, 1.0)) * 10

    Rank:
        ROW_NUMBER() OVER (
            PARTITION BY ranking_date
            ORDER BY demand_score DESC, station_id ASC
        )

    Category:
        HIGH   if demand_score >= 30
        MEDIUM if demand_score >= 15
        LOW    otherwise

    Returns:
        Number of rows inserted/upserted.
    """
    clean_date = _validate_target_date(target_date)

    logger.info(
        f"Building mart.station_demand_ranking for target_date={clean_date}, "
        f"batch_id={batch_id}, run_id={run_id}"
    )

    sql = """
        WITH station_scores AS (
            SELECT
                dss.summary_date AS ranking_date,
                dss.station_id,
                dss.station_name,
                dss.region_id,
                dss.region_name,
                dss.capacity,
                dss.active_hour_count,
                dss.total_observation_count,
                dss.avg_bikes_available,
                dss.avg_docks_available,
                dss.avg_availability_rate,
                dss.avg_dock_utilization_rate,
                dss.empty_hour_count,
                dss.full_hour_count,
                dss.low_availability_hour_count,
                dss.high_demand_hour_count,
                dss.is_weekend,
                dss.is_holiday,
                dss.holiday_name,

                (
                    (COALESCE(dss.low_availability_hour_count, 0) * 3)
                    + (COALESCE(dss.empty_hour_count, 0) * 5)
                    + (COALESCE(dss.full_hour_count, 0) * 1)
                    + (
                        (1.0 - COALESCE(dss.avg_availability_rate, 1.0))
                        * 10
                    )
                ) AS demand_score

            FROM mart.daily_station_summary dss
            WHERE dss.summary_date = CAST(:target_date AS DATE)
        ),

        ranked_stations AS (
            SELECT
                ss.*,
                ROW_NUMBER() OVER (
                    PARTITION BY ss.ranking_date
                    ORDER BY ss.demand_score DESC, ss.station_id ASC
                ) AS demand_rank,

                CASE
                    WHEN ss.demand_score >= 30 THEN 'HIGH'
                    WHEN ss.demand_score >= 15 THEN 'MEDIUM'
                    ELSE 'LOW'
                END AS demand_category

            FROM station_scores ss
        )

        INSERT INTO mart.station_demand_ranking (
            ranking_date,
            station_id,
            station_name,
            region_id,
            region_name,
            capacity,
            active_hour_count,
            total_observation_count,
            avg_bikes_available,
            avg_docks_available,
            avg_availability_rate,
            avg_dock_utilization_rate,
            empty_hour_count,
            full_hour_count,
            low_availability_hour_count,
            high_demand_hour_count,
            demand_score,
            demand_rank,
            demand_category,
            is_weekend,
            is_holiday,
            holiday_name,
            batch_id,
            run_id,
            updated_at
        )
        SELECT
            rs.ranking_date,
            rs.station_id,
            rs.station_name,
            rs.region_id,
            rs.region_name,
            rs.capacity,
            rs.active_hour_count,
            rs.total_observation_count,
            rs.avg_bikes_available,
            rs.avg_docks_available,
            rs.avg_availability_rate,
            rs.avg_dock_utilization_rate,
            rs.empty_hour_count,
            rs.full_hour_count,
            rs.low_availability_hour_count,
            rs.high_demand_hour_count,
            rs.demand_score,
            rs.demand_rank,
            rs.demand_category,
            rs.is_weekend,
            rs.is_holiday,
            rs.holiday_name,
            :batch_id AS batch_id,
            :run_id AS run_id,
            CURRENT_TIMESTAMP AS updated_at

        FROM ranked_stations rs

        ON CONFLICT (ranking_date, station_id) DO UPDATE SET
            station_name = EXCLUDED.station_name,
            region_id = EXCLUDED.region_id,
            region_name = EXCLUDED.region_name,
            capacity = EXCLUDED.capacity,
            active_hour_count = EXCLUDED.active_hour_count,
            total_observation_count = EXCLUDED.total_observation_count,
            avg_bikes_available = EXCLUDED.avg_bikes_available,
            avg_docks_available = EXCLUDED.avg_docks_available,
            avg_availability_rate = EXCLUDED.avg_availability_rate,
            avg_dock_utilization_rate = EXCLUDED.avg_dock_utilization_rate,
            empty_hour_count = EXCLUDED.empty_hour_count,
            full_hour_count = EXCLUDED.full_hour_count,
            low_availability_hour_count = EXCLUDED.low_availability_hour_count,
            high_demand_hour_count = EXCLUDED.high_demand_hour_count,
            demand_score = EXCLUDED.demand_score,
            demand_rank = EXCLUDED.demand_rank,
            demand_category = EXCLUDED.demand_category,
            is_weekend = EXCLUDED.is_weekend,
            is_holiday = EXCLUDED.is_holiday,
            holiday_name = EXCLUDED.holiday_name,
            batch_id = EXCLUDED.batch_id,
            run_id = EXCLUDED.run_id,
            updated_at = CURRENT_TIMESTAMP
    """

    params = {
        "target_date": clean_date,
        "batch_id": batch_id,
        "run_id": run_id,
    }

    count = execute_sql(sql, params)

    logger.info(
        f"Built mart.station_demand_ranking for target_date={clean_date}. "
        f"records_processed={count}"
    )

    return count


def build_daily_system_summary(
    target_date: str,
    batch_id: str,
    run_id: str,
) -> int:
    """
    Build mart.daily_system_summary for the target summary date.

    Grain:
        1 row / summary_date

    Source:
        mart.daily_station_summary

    Weather metric design:
        System-level weather metrics are aggregated from station-level
        observed weather metrics.

        total_precipitation is calculated as AVG of station-level
        total_precipitation to avoid multiplying the same weather source by
        station_count.

    Returns:
        Number of rows inserted/upserted.
    """
    clean_date = _validate_target_date(target_date)

    logger.info(
        f"Building mart.daily_system_summary for target_date={clean_date}, "
        f"batch_id={batch_id}, run_id={run_id}"
    )

    sql = """
        INSERT INTO mart.daily_system_summary (
            summary_date,
            station_count,
            active_station_count,
            region_count,
            total_observation_count,
            avg_bikes_available,
            avg_docks_available,
            total_bikes_available,
            total_docks_available,
            avg_availability_rate,
            avg_dock_utilization_rate,
            empty_station_count,
            full_station_count,
            low_availability_station_count,
            high_demand_station_count,
            avg_temperature,
            total_precipitation,
            avg_wind_speed,
            is_weekend,
            is_holiday,
            holiday_name,
            batch_id,
            run_id,
            updated_at
        )
        SELECT
            dss.summary_date,

            COUNT(DISTINCT dss.station_id) AS station_count,

            COUNT(
                DISTINCT CASE
                    WHEN dss.active_hour_count > 0 THEN dss.station_id
                END
            ) AS active_station_count,

            COUNT(DISTINCT COALESCE(dss.region_id, 'UNKNOWN')) AS region_count,

            SUM(dss.total_observation_count) AS total_observation_count,

            AVG(dss.avg_bikes_available) AS avg_bikes_available,
            AVG(dss.avg_docks_available) AS avg_docks_available,

            SUM(dss.avg_bikes_available) AS total_bikes_available,
            SUM(dss.avg_docks_available) AS total_docks_available,

            CASE
                WHEN AVG(dss.avg_availability_rate) IS NULL THEN NULL
                ELSE LEAST(1.0, GREATEST(0.0, AVG(dss.avg_availability_rate)))
            END AS avg_availability_rate,

            CASE
                WHEN AVG(dss.avg_dock_utilization_rate) IS NULL THEN NULL
                ELSE LEAST(1.0, GREATEST(0.0, AVG(dss.avg_dock_utilization_rate)))
            END AS avg_dock_utilization_rate,

            COUNT(CASE WHEN dss.avg_bikes_available = 0 THEN 1 END) AS empty_station_count,
            COUNT(CASE WHEN dss.avg_docks_available = 0 THEN 1 END) AS full_station_count,
            COUNT(CASE WHEN dss.avg_availability_rate < 0.2 THEN 1 END) AS low_availability_station_count,
            COUNT(CASE WHEN dss.high_demand_hour_count > 0 THEN 1 END) AS high_demand_station_count,

            AVG(dss.avg_temperature) AS avg_temperature,
            AVG(dss.total_precipitation) AS total_precipitation,
            AVG(dss.avg_wind_speed) AS avg_wind_speed,

            BOOL_OR(dss.is_weekend) AS is_weekend,
            BOOL_OR(dss.is_holiday) AS is_holiday,
            MAX(dss.holiday_name) AS holiday_name,

            :batch_id AS batch_id,
            :run_id AS run_id,
            CURRENT_TIMESTAMP AS updated_at

        FROM mart.daily_station_summary dss
        WHERE dss.summary_date = CAST(:target_date AS DATE)
        GROUP BY
            dss.summary_date

        ON CONFLICT (summary_date) DO UPDATE SET
            station_count = EXCLUDED.station_count,
            active_station_count = EXCLUDED.active_station_count,
            region_count = EXCLUDED.region_count,
            total_observation_count = EXCLUDED.total_observation_count,
            avg_bikes_available = EXCLUDED.avg_bikes_available,
            avg_docks_available = EXCLUDED.avg_docks_available,
            total_bikes_available = EXCLUDED.total_bikes_available,
            total_docks_available = EXCLUDED.total_docks_available,
            avg_availability_rate = EXCLUDED.avg_availability_rate,
            avg_dock_utilization_rate = EXCLUDED.avg_dock_utilization_rate,
            empty_station_count = EXCLUDED.empty_station_count,
            full_station_count = EXCLUDED.full_station_count,
            low_availability_station_count = EXCLUDED.low_availability_station_count,
            high_demand_station_count = EXCLUDED.high_demand_station_count,
            avg_temperature = EXCLUDED.avg_temperature,
            total_precipitation = EXCLUDED.total_precipitation,
            avg_wind_speed = EXCLUDED.avg_wind_speed,
            is_weekend = EXCLUDED.is_weekend,
            is_holiday = EXCLUDED.is_holiday,
            holiday_name = EXCLUDED.holiday_name,
            batch_id = EXCLUDED.batch_id,
            run_id = EXCLUDED.run_id,
            updated_at = CURRENT_TIMESTAMP
    """

    params = {
        "target_date": clean_date,
        "batch_id": batch_id,
        "run_id": run_id,
    }

    count = execute_sql(sql, params)

    logger.info(
        f"Built mart.daily_system_summary for target_date={clean_date}. "
        f"records_processed={count}"
    )

    return count