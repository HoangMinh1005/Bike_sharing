from datetime import date
from api.services.freshness_service import (
    evaluate_station_status_freshness,
    evaluate_hourly_mart_freshness,
    evaluate_daily_summary_freshness,
    calculate_overall_status,
)


def test_station_status_freshness_thresholds():
    # Healthy: <= 30 minutes
    assert evaluate_station_status_freshness(0.0) == "HEALTHY"
    assert evaluate_station_status_freshness(15.0) == "HEALTHY"
    assert evaluate_station_status_freshness(30.0) == "HEALTHY"

    # Warning: 30 to 60 minutes
    assert evaluate_station_status_freshness(30.1) == "WARNING"
    assert evaluate_station_status_freshness(45.0) == "WARNING"
    assert evaluate_station_status_freshness(60.0) == "WARNING"

    # Stale: > 60 minutes
    assert evaluate_station_status_freshness(60.1) == "STALE"
    assert evaluate_station_status_freshness(120.0) == "STALE"

    # Unknown: None or negative
    assert evaluate_station_status_freshness(None) == "UNKNOWN"
    assert evaluate_station_status_freshness(-5.0) == "UNKNOWN"


def test_hourly_mart_freshness_thresholds():
    # Healthy: <= 120 minutes (2 hours)
    assert evaluate_hourly_mart_freshness(0.0) == "HEALTHY"
    assert evaluate_hourly_mart_freshness(60.0) == "HEALTHY"
    assert evaluate_hourly_mart_freshness(120.0) == "HEALTHY"

    # Warning: 120 to 240 minutes (2 to 4 hours)
    assert evaluate_hourly_mart_freshness(120.1) == "WARNING"
    assert evaluate_hourly_mart_freshness(180.0) == "WARNING"
    assert evaluate_hourly_mart_freshness(240.0) == "WARNING"

    # Stale: > 240 minutes
    assert evaluate_hourly_mart_freshness(240.1) == "STALE"
    assert evaluate_hourly_mart_freshness(500.0) == "STALE"

    # Unknown: None
    assert evaluate_hourly_mart_freshness(None) == "UNKNOWN"


def test_daily_summary_freshness_thresholds():
    today = date(2026, 8, 13)

    # Healthy: Today or yesterday (<= 1 day)
    assert evaluate_daily_summary_freshness(date(2026, 8, 13), today) == "HEALTHY"
    assert evaluate_daily_summary_freshness(date(2026, 8, 12), today) == "HEALTHY"

    # Warning: 2 days ago
    assert evaluate_daily_summary_freshness(date(2026, 8, 11), today) == "WARNING"

    # Stale: > 2 days ago
    assert evaluate_daily_summary_freshness(date(2026, 8, 10), today) == "STALE"
    assert evaluate_daily_summary_freshness(date(2026, 8, 1), today) == "STALE"

    # Unknown: None
    assert evaluate_daily_summary_freshness(None, today) == "UNKNOWN"


def test_calculate_overall_status():
    # All healthy -> HEALTHY
    assert calculate_overall_status(["HEALTHY", "HEALTHY", "HEALTHY"]) == "HEALTHY"

    # Any warning -> WARNING
    assert calculate_overall_status(["HEALTHY", "WARNING", "HEALTHY"]) == "WARNING"

    # Any stale -> STALE
    assert calculate_overall_status(["HEALTHY", "WARNING", "STALE"]) == "STALE"

    # Any unknown -> UNKNOWN
    assert calculate_overall_status(["HEALTHY", "STALE", "UNKNOWN"]) == "UNKNOWN"
    assert calculate_overall_status([]) == "UNKNOWN"
