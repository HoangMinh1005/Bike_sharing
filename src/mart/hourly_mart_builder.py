import pendulum

from src.common.db import execute_sql
from src.common.logger import get_logger

logger = get_logger(__name__)


def _validate_target_window(
    target_hour_start: str,
    target_hour_end: str,
) -> None:
    """
    Validate target hourly mart build window.

    The mart builder should only build for a valid time range:
    target_hour_start < target_hour_end
    """
    try:
        start = pendulum.parse(target_hour_start)
        end = pendulum.parse(target_hour_end)
    except Exception as e:
        raise ValueError(
            f"Invalid target hour format. "
            f"target_hour_start={target_hour_start}, "
            f"target_hour_end={target_hour_end}, error={e}"
        ) from e

    if start >= end:
        raise ValueError(
            f"Invalid target hour window: "
            f"target_hour_start={target_hour_start} must be earlier than "
            f"target_hour_end={target_hour_end}"
        )


def build_hourly_station_availability(
    target_hour_start: str,
    target_hour_end: str,
    batch_id: str,
    run_id: str,
) -> int:
    """
    Build mart.hourly_station_availability for the target hour window.

    Grain:
        1 row / station_id / hour_bucket

    Source:
        - staging.station_status
        - staging.stations
        - staging.regions
        - staging.weather_hourly
        - staging.calendar

    Notes:
        - hour_bucket is calculated from COALESCE(last_reported, fetched_at).
        - weather/calendar are LEFT JOIN enrichment sources.
        - Missing weather/calendar should not remove station rows.
        - dock_utilization_rate here means station occupied/unavailable-dock ratio:
          (capacity - avg_docks_available) / capacity.
    """
    _validate_target_window(target_hour_start, target_hour_end)

    logger.info(
        f"Building mart.hourly_station_availability. "
        f"window=[{target_hour_start} to {target_hour_end}], "
        f"batch_id={batch_id}, run_id={run_id}"
    )

    sql = """
        WITH station_status_filtered AS (
            SELECT
                station_id,
                num_bikes_available,
                num_docks_available,
                num_bikes_disabled,
                num_docks_disabled,
                is_installed,
                is_renting,
                is_returning,
                COALESCE(last_reported, fetched_at) AS obs_time,
                date_trunc('hour', COALESCE(last_reported, fetched_at)) AS hour_bucket
            FROM staging.station_status
            WHERE COALESCE(last_reported, fetched_at) >= CAST(:target_hour_start AS TIMESTAMP)
              AND COALESCE(last_reported, fetched_at) < CAST(:target_hour_end AS TIMESTAMP)
        ),

        station_aggregated AS (
            SELECT
                sf.hour_bucket,
                sf.station_id,
                COUNT(*) AS observation_count,
                AVG(sf.num_bikes_available) AS avg_bikes_available,
                AVG(sf.num_docks_available) AS avg_docks_available,
                AVG(sf.num_bikes_disabled) AS avg_bikes_disabled,
                AVG(sf.num_docks_disabled) AS avg_docks_disabled,
                MIN(sf.num_bikes_available) AS min_bikes_available,
                MAX(sf.num_bikes_available) AS max_bikes_available,
                COUNT(CASE WHEN sf.num_bikes_available = 0 THEN 1 END) AS empty_observation_count,
                COUNT(CASE WHEN sf.num_docks_available = 0 THEN 1 END) AS full_observation_count,
                BOOL_OR(sf.is_installed) AS is_installed,
                BOOL_OR(sf.is_renting) AS is_renting,
                BOOL_OR(sf.is_returning) AS is_returning
            FROM station_status_filtered sf
            GROUP BY
                sf.hour_bucket,
                sf.station_id
        ),

        weather_deduped AS (
            /*
             MVP assumption:
             staging.weather_hourly contains one configured weather location,
             for example Brooklyn.
            */
            SELECT DISTINCT ON (date_trunc('hour', weather_time))
                date_trunc('hour', weather_time) AS weather_hour,
                temperature,
                humidity,
                precipitation,
                wind_speed,
                weather_code
            FROM staging.weather_hourly
            WHERE weather_time >= CAST(:target_hour_start AS TIMESTAMP)
              AND weather_time < CAST(:target_hour_end AS TIMESTAMP)
            ORDER BY
                date_trunc('hour', weather_time),
                updated_at DESC
        ),

        calendar_deduped AS (
            SELECT DISTINCT ON (calendar_date)
                calendar_date,
                day_of_week,
                is_weekend,
                is_holiday,
                holiday_name
            FROM staging.calendar
            WHERE calendar_date >= DATE(CAST(:target_hour_start AS TIMESTAMP))
              AND calendar_date <= DATE(CAST(:target_hour_end AS TIMESTAMP))
            ORDER BY
                calendar_date,
                updated_at DESC
        ),

        station_enriched AS (
            SELECT
                sa.hour_bucket,
                sa.station_id,
                s.station_name,
                COALESCE(s.region_id, 'UNKNOWN') AS region_id,
                COALESCE(r.region_name, 'Unknown Region') AS region_name,
                s.latitude,
                s.longitude,

                COALESCE(
                    s.capacity,
                    CAST(
                        ROUND(
                            sa.avg_bikes_available
                            + sa.avg_docks_available
                            + sa.avg_bikes_disabled
                            + sa.avg_docks_disabled
                        ) AS INTEGER
                    )
                ) AS capacity,

                sa.observation_count,
                sa.avg_bikes_available,
                sa.avg_docks_available,
                sa.avg_bikes_disabled,
                sa.avg_docks_disabled,
                sa.min_bikes_available,
                sa.max_bikes_available,
                sa.empty_observation_count,
                sa.full_observation_count,
                sa.is_installed,
                sa.is_renting,
                sa.is_returning,

                w.temperature,
                w.humidity,
                w.precipitation,
                w.wind_speed,
                w.weather_code,

                c.calendar_date,
                c.day_of_week,
                c.is_weekend,
                c.is_holiday,
                c.holiday_name
            FROM station_aggregated sa
            LEFT JOIN staging.stations s
                ON sa.station_id = s.station_id
            LEFT JOIN staging.regions r
                ON s.region_id = r.region_id
            LEFT JOIN weather_deduped w
                ON sa.hour_bucket = w.weather_hour
            LEFT JOIN calendar_deduped c
                ON DATE(sa.hour_bucket) = c.calendar_date
        )

        INSERT INTO mart.hourly_station_availability (
            hour_bucket,
            station_id,
            station_name,
            region_id,
            region_name,
            latitude,
            longitude,
            capacity,
            observation_count,
            avg_bikes_available,
            avg_docks_available,
            avg_bikes_disabled,
            avg_docks_disabled,
            min_bikes_available,
            max_bikes_available,
            empty_observation_count,
            full_observation_count,
            availability_rate,
            dock_utilization_rate,
            is_installed,
            is_renting,
            is_returning,
            temperature,
            humidity,
            precipitation,
            wind_speed,
            weather_code,
            calendar_date,
            day_of_week,
            is_weekend,
            is_holiday,
            holiday_name,
            batch_id,
            run_id,
            updated_at
        )
        SELECT
            se.hour_bucket,
            se.station_id,
            se.station_name,
            se.region_id,
            se.region_name,
            se.latitude,
            se.longitude,
            se.capacity,
            se.observation_count,
            se.avg_bikes_available,
            se.avg_docks_available,
            se.avg_bikes_disabled,
            se.avg_docks_disabled,
            se.min_bikes_available,
            se.max_bikes_available,
            se.empty_observation_count,
            se.full_observation_count,

            CASE
                WHEN se.capacity IS NULL OR se.capacity <= 0 THEN NULL
                ELSE LEAST(
                    1.0,
                    GREATEST(
                        0.0,
                        se.avg_bikes_available / NULLIF(se.capacity, 0)
                    )
                )
            END AS availability_rate,

            CASE
                WHEN se.capacity IS NULL OR se.capacity <= 0 THEN NULL
                ELSE LEAST(
                    1.0,
                    GREATEST(
                        0.0,
                        (se.capacity - se.avg_docks_available) / NULLIF(se.capacity, 0)
                    )
                )
            END AS dock_utilization_rate,

            se.is_installed,
            se.is_renting,
            se.is_returning,
            se.temperature,
            se.humidity,
            se.precipitation,
            se.wind_speed,
            se.weather_code,
            se.calendar_date,
            se.day_of_week,
            se.is_weekend,
            se.is_holiday,
            se.holiday_name,
            :batch_id AS batch_id,
            :run_id AS run_id,
            CURRENT_TIMESTAMP AS updated_at
        FROM station_enriched se

        ON CONFLICT (hour_bucket, station_id) DO UPDATE SET
            station_name = EXCLUDED.station_name,
            region_id = EXCLUDED.region_id,
            region_name = EXCLUDED.region_name,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            capacity = EXCLUDED.capacity,
            observation_count = EXCLUDED.observation_count,
            avg_bikes_available = EXCLUDED.avg_bikes_available,
            avg_docks_available = EXCLUDED.avg_docks_available,
            avg_bikes_disabled = EXCLUDED.avg_bikes_disabled,
            avg_docks_disabled = EXCLUDED.avg_docks_disabled,
            min_bikes_available = EXCLUDED.min_bikes_available,
            max_bikes_available = EXCLUDED.max_bikes_available,
            empty_observation_count = EXCLUDED.empty_observation_count,
            full_observation_count = EXCLUDED.full_observation_count,
            availability_rate = EXCLUDED.availability_rate,
            dock_utilization_rate = EXCLUDED.dock_utilization_rate,
            is_installed = EXCLUDED.is_installed,
            is_renting = EXCLUDED.is_renting,
            is_returning = EXCLUDED.is_returning,
            temperature = EXCLUDED.temperature,
            humidity = EXCLUDED.humidity,
            precipitation = EXCLUDED.precipitation,
            wind_speed = EXCLUDED.wind_speed,
            weather_code = EXCLUDED.weather_code,
            calendar_date = EXCLUDED.calendar_date,
            day_of_week = EXCLUDED.day_of_week,
            is_weekend = EXCLUDED.is_weekend,
            is_holiday = EXCLUDED.is_holiday,
            holiday_name = EXCLUDED.holiday_name,
            batch_id = EXCLUDED.batch_id,
            run_id = EXCLUDED.run_id,
            updated_at = CURRENT_TIMESTAMP
    """

    params = {
        "target_hour_start": target_hour_start,
        "target_hour_end": target_hour_end,
        "batch_id": batch_id,
        "run_id": run_id,
    }

    count = execute_sql(sql, params)

    logger.info(
        f"Built mart.hourly_station_availability. "
        f"records_processed={count}"
    )

    return count


def build_hourly_region_availability(
    target_hour_start: str,
    target_hour_end: str,
    batch_id: str,
    run_id: str,
) -> int:
    """
    Build mart.hourly_region_availability for the target hour window.

    Grain:
        1 row / region_id / hour_bucket

    Source:
        mart.hourly_station_availability
    """
    _validate_target_window(target_hour_start, target_hour_end)

    logger.info(
        f"Building mart.hourly_region_availability. "
        f"window=[{target_hour_start} to {target_hour_end}], "
        f"batch_id={batch_id}, run_id={run_id}"
    )

    sql = """
        INSERT INTO mart.hourly_region_availability (
            hour_bucket,
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
            temperature,
            humidity,
            precipitation,
            wind_speed,
            weather_code,
            calendar_date,
            day_of_week,
            is_weekend,
            is_holiday,
            batch_id,
            run_id,
            updated_at
        )
        SELECT
            hsa.hour_bucket,
            COALESCE(hsa.region_id, 'UNKNOWN') AS region_id,
            COALESCE(MAX(hsa.region_name), 'Unknown Region') AS region_name,
            COUNT(DISTINCT hsa.station_id) AS station_count,

            COUNT(
                DISTINCT CASE
                    WHEN hsa.is_installed
                     AND hsa.is_renting
                     AND hsa.is_returning
                    THEN hsa.station_id
                END
            ) AS active_station_count,

            SUM(hsa.observation_count) AS total_observation_count,
            AVG(hsa.avg_bikes_available) AS avg_bikes_available,
            AVG(hsa.avg_docks_available) AS avg_docks_available,
            SUM(hsa.avg_bikes_available) AS total_bikes_available,
            SUM(hsa.avg_docks_available) AS total_docks_available,

            CASE
                WHEN AVG(hsa.availability_rate) IS NULL THEN NULL
                ELSE LEAST(1.0, GREATEST(0.0, AVG(hsa.availability_rate)))
            END AS avg_availability_rate,

            CASE
                WHEN AVG(hsa.dock_utilization_rate) IS NULL THEN NULL
                ELSE LEAST(1.0, GREATEST(0.0, AVG(hsa.dock_utilization_rate)))
            END AS avg_dock_utilization_rate,

            COUNT(CASE WHEN hsa.avg_bikes_available = 0 THEN 1 END) AS empty_station_count,
            COUNT(CASE WHEN hsa.avg_docks_available = 0 THEN 1 END) AS full_station_count,

            MAX(hsa.temperature) AS temperature,
            MAX(hsa.humidity) AS humidity,
            MAX(hsa.precipitation) AS precipitation,
            MAX(hsa.wind_speed) AS wind_speed,
            MAX(hsa.weather_code) AS weather_code,
            MAX(hsa.calendar_date) AS calendar_date,
            MAX(hsa.day_of_week) AS day_of_week,
            BOOL_OR(hsa.is_weekend) AS is_weekend,
            BOOL_OR(hsa.is_holiday) AS is_holiday,

            :batch_id AS batch_id,
            :run_id AS run_id,
            CURRENT_TIMESTAMP AS updated_at

        FROM mart.hourly_station_availability hsa
        WHERE hsa.hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
          AND hsa.hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
        GROUP BY
            hsa.hour_bucket,
            COALESCE(hsa.region_id, 'UNKNOWN')

        ON CONFLICT (hour_bucket, region_id) DO UPDATE SET
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
            temperature = EXCLUDED.temperature,
            humidity = EXCLUDED.humidity,
            precipitation = EXCLUDED.precipitation,
            wind_speed = EXCLUDED.wind_speed,
            weather_code = EXCLUDED.weather_code,
            calendar_date = EXCLUDED.calendar_date,
            day_of_week = EXCLUDED.day_of_week,
            is_weekend = EXCLUDED.is_weekend,
            is_holiday = EXCLUDED.is_holiday,
            batch_id = EXCLUDED.batch_id,
            run_id = EXCLUDED.run_id,
            updated_at = CURRENT_TIMESTAMP
    """

    params = {
        "target_hour_start": target_hour_start,
        "target_hour_end": target_hour_end,
        "batch_id": batch_id,
        "run_id": run_id,
    }

    count = execute_sql(sql, params)

    logger.info(
        f"Built mart.hourly_region_availability. "
        f"records_processed={count}"
    )

    return count


def build_vehicle_type_availability_summary(
    target_hour_start: str,
    target_hour_end: str,
    batch_id: str,
    run_id: str,
) -> int:
    """
    Build mart.vehicle_type_availability_summary for the target hour window.

    Grain:
        1 row / vehicle_type_id / hour_bucket

    Important:
        staging.station_vehicle_type_status may contain multiple snapshots
        in one hour. Therefore, this function first aggregates per
        station_id + vehicle_type_id + hour_bucket, then aggregates again
        to vehicle_type_id + hour_bucket.

        This avoids over-counting when the pipeline has multiple station
        snapshots within the same hour.
    """
    _validate_target_window(target_hour_start, target_hour_end)

    logger.info(
        f"Building mart.vehicle_type_availability_summary. "
        f"window=[{target_hour_start} to {target_hour_end}], "
        f"batch_id={batch_id}, run_id={run_id}"
    )

    sql = """
        WITH vt_filtered AS (
            SELECT
                svts.station_id,
                svts.vehicle_type_id,
                svts.count,
                date_trunc(
                    'hour',
                    COALESCE(svts.last_reported, svts.fetched_at)
                ) AS hour_bucket
            FROM staging.station_vehicle_type_status svts
            WHERE COALESCE(svts.last_reported, svts.fetched_at) >= CAST(:target_hour_start AS TIMESTAMP)
              AND COALESCE(svts.last_reported, svts.fetched_at) < CAST(:target_hour_end AS TIMESTAMP)
        ),

        vt_station_hourly AS (
            SELECT
                vf.hour_bucket,
                vf.station_id,
                vf.vehicle_type_id,
                AVG(vf.count) AS avg_vehicle_count
            FROM vt_filtered vf
            GROUP BY
                vf.hour_bucket,
                vf.station_id,
                vf.vehicle_type_id
        )

        INSERT INTO mart.vehicle_type_availability_summary (
            hour_bucket,
            vehicle_type_id,
            vehicle_type_form_factor,
            propulsion_type,
            station_count,
            total_vehicle_count,
            avg_vehicle_count_per_station,
            min_vehicle_count,
            max_vehicle_count,
            batch_id,
            run_id,
            updated_at
        )
        SELECT
            vsh.hour_bucket,
            vsh.vehicle_type_id,
            MAX(vt.form_factor) AS vehicle_type_form_factor,
            MAX(vt.propulsion_type) AS propulsion_type,
            COUNT(DISTINCT vsh.station_id) AS station_count,
            SUM(vsh.avg_vehicle_count) AS total_vehicle_count,
            AVG(vsh.avg_vehicle_count) AS avg_vehicle_count_per_station,
            MIN(vsh.avg_vehicle_count) AS min_vehicle_count,
            MAX(vsh.avg_vehicle_count) AS max_vehicle_count,
            :batch_id AS batch_id,
            :run_id AS run_id,
            CURRENT_TIMESTAMP AS updated_at
        FROM vt_station_hourly vsh
        LEFT JOIN staging.vehicle_types vt
            ON vsh.vehicle_type_id = vt.vehicle_type_id
        GROUP BY
            vsh.hour_bucket,
            vsh.vehicle_type_id

        ON CONFLICT (hour_bucket, vehicle_type_id) DO UPDATE SET
            vehicle_type_form_factor = EXCLUDED.vehicle_type_form_factor,
            propulsion_type = EXCLUDED.propulsion_type,
            station_count = EXCLUDED.station_count,
            total_vehicle_count = EXCLUDED.total_vehicle_count,
            avg_vehicle_count_per_station = EXCLUDED.avg_vehicle_count_per_station,
            min_vehicle_count = EXCLUDED.min_vehicle_count,
            max_vehicle_count = EXCLUDED.max_vehicle_count,
            batch_id = EXCLUDED.batch_id,
            run_id = EXCLUDED.run_id,
            updated_at = CURRENT_TIMESTAMP
    """

    params = {
        "target_hour_start": target_hour_start,
        "target_hour_end": target_hour_end,
        "batch_id": batch_id,
        "run_id": run_id,
    }

    count = execute_sql(sql, params)

    logger.info(
        f"Built mart.vehicle_type_availability_summary. "
        f"records_processed={count}"
    )

    return count


def build_weather_mobility_summary(
    target_hour_start: str,
    target_hour_end: str,
    batch_id: str,
    run_id: str,
) -> int:
    """
    Build mart.weather_mobility_summary for the target hour window.

    Grain:
        1 row / hour_bucket

    Source:
        mart.hourly_station_availability
    """
    _validate_target_window(target_hour_start, target_hour_end)

    logger.info(
        f"Building mart.weather_mobility_summary. "
        f"window=[{target_hour_start} to {target_hour_end}], "
        f"batch_id={batch_id}, run_id={run_id}"
    )

    sql = """
        INSERT INTO mart.weather_mobility_summary (
            hour_bucket,
            station_count,
            active_station_count,
            total_bikes_available,
            total_docks_available,
            avg_availability_rate,
            avg_dock_utilization_rate,
            empty_station_count,
            full_station_count,
            temperature,
            humidity,
            precipitation,
            wind_speed,
            weather_code,
            calendar_date,
            day_of_week,
            is_weekend,
            is_holiday,
            holiday_name,
            batch_id,
            run_id,
            updated_at
        )
        SELECT
            hsa.hour_bucket,
            COUNT(DISTINCT hsa.station_id) AS station_count,

            COUNT(
                DISTINCT CASE
                    WHEN hsa.is_installed
                     AND hsa.is_renting
                     AND hsa.is_returning
                    THEN hsa.station_id
                END
            ) AS active_station_count,

            SUM(hsa.avg_bikes_available) AS total_bikes_available,
            SUM(hsa.avg_docks_available) AS total_docks_available,

            CASE
                WHEN AVG(hsa.availability_rate) IS NULL THEN NULL
                ELSE LEAST(1.0, GREATEST(0.0, AVG(hsa.availability_rate)))
            END AS avg_availability_rate,

            CASE
                WHEN AVG(hsa.dock_utilization_rate) IS NULL THEN NULL
                ELSE LEAST(1.0, GREATEST(0.0, AVG(hsa.dock_utilization_rate)))
            END AS avg_dock_utilization_rate,

            COUNT(CASE WHEN hsa.avg_bikes_available = 0 THEN 1 END) AS empty_station_count,
            COUNT(CASE WHEN hsa.avg_docks_available = 0 THEN 1 END) AS full_station_count,

            MAX(hsa.temperature) AS temperature,
            MAX(hsa.humidity) AS humidity,
            MAX(hsa.precipitation) AS precipitation,
            MAX(hsa.wind_speed) AS wind_speed,
            MAX(hsa.weather_code) AS weather_code,
            MAX(hsa.calendar_date) AS calendar_date,
            MAX(hsa.day_of_week) AS day_of_week,
            BOOL_OR(hsa.is_weekend) AS is_weekend,
            BOOL_OR(hsa.is_holiday) AS is_holiday,
            MAX(hsa.holiday_name) AS holiday_name,

            :batch_id AS batch_id,
            :run_id AS run_id,
            CURRENT_TIMESTAMP AS updated_at

        FROM mart.hourly_station_availability hsa
        WHERE hsa.hour_bucket >= CAST(:target_hour_start AS TIMESTAMP)
          AND hsa.hour_bucket < CAST(:target_hour_end AS TIMESTAMP)
        GROUP BY
            hsa.hour_bucket

        ON CONFLICT (hour_bucket) DO UPDATE SET
            station_count = EXCLUDED.station_count,
            active_station_count = EXCLUDED.active_station_count,
            total_bikes_available = EXCLUDED.total_bikes_available,
            total_docks_available = EXCLUDED.total_docks_available,
            avg_availability_rate = EXCLUDED.avg_availability_rate,
            avg_dock_utilization_rate = EXCLUDED.avg_dock_utilization_rate,
            empty_station_count = EXCLUDED.empty_station_count,
            full_station_count = EXCLUDED.full_station_count,
            temperature = EXCLUDED.temperature,
            humidity = EXCLUDED.humidity,
            precipitation = EXCLUDED.precipitation,
            wind_speed = EXCLUDED.wind_speed,
            weather_code = EXCLUDED.weather_code,
            calendar_date = EXCLUDED.calendar_date,
            day_of_week = EXCLUDED.day_of_week,
            is_weekend = EXCLUDED.is_weekend,
            is_holiday = EXCLUDED.is_holiday,
            holiday_name = EXCLUDED.holiday_name,
            batch_id = EXCLUDED.batch_id,
            run_id = EXCLUDED.run_id,
            updated_at = CURRENT_TIMESTAMP
    """

    params = {
        "target_hour_start": target_hour_start,
        "target_hour_end": target_hour_end,
        "batch_id": batch_id,
        "run_id": run_id,
    }

    count = execute_sql(sql, params)

    logger.info(
        f"Built mart.weather_mobility_summary. "
        f"records_processed={count}"
    )

    return count