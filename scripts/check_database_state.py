import sys
from src.common.db import fetch_one
from src.common.logger import get_logger

logger = get_logger(__name__)

TARGET_TABLES = [
    # Raw Layer
    "raw.gbfs_feed_snapshots",
    "raw.station_status_snapshots",
    "raw.weather_hourly",
    "raw.calendar",
    # Staging Layer
    "staging.stations",
    "staging.station_status",
    "staging.station_vehicle_type_status",
    "staging.weather_hourly",
    "staging.calendar",
    # Hourly Mart Layer
    "mart.hourly_station_availability",
    "mart.hourly_region_availability",
    "mart.vehicle_type_availability_summary",
    "mart.weather_mobility_summary",
    # Daily Mart Layer
    "mart.daily_station_summary",
    "mart.daily_region_summary",
    "mart.daily_system_summary",
    "mart.station_demand_ranking",
    # Metadata Layer
    "etl_metadata.pipeline_runs",
    "etl_metadata.dq_results",
    "etl_metadata.watermarks",
    "etl_metadata.pipeline_health_summary",
]


def check_database_state() -> None:
    """
    Utility script to inspect database table row counts across all layers.
    """
    print("=" * 70)
    print("BIKE SHARING OPERATION INTELLIGENCE — DATABASE STATE CHECK")
    print("=" * 70)
    print(f"{'TABLE NAME':<42} | {'ROW COUNT':<12} | {'STATUS'}")
    print("-" * 70)

    ok_count = 0
    error_count = 0

    for table in TARGET_TABLES:
        try:
            sql = f"SELECT COUNT(*) AS count FROM {table}"
            res = fetch_one(sql)
            count = int(res["count"] or 0) if res else 0
            status = "OK"
            ok_count += 1
            print(f"{table:<42} | {count:<12,} | {status}")
        except Exception as e:
            status = f"ERROR ({type(e).__name__})"
            error_count += 1
            print(f"{table:<42} | {'N/A':<12} | {status}")

    print("=" * 70)
    print(f"SUMMARY: {ok_count} table(s) OK | {error_count} table(s) ERROR")
    print("=" * 70)


if __name__ == "__main__":
    check_database_state()
