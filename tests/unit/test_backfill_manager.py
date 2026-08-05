import pendulum
import pytest

from src.backfill.backfill_manager import (
    generate_daily_dates,
    generate_hourly_windows,
    parse_backfill_conf,
)


def test_parse_hourly_config_valid():
    """
    Test parsing valid hourly backfill configuration.
    """
    conf = {
        "backfill_type": "hourly",
        "start": "2026-07-01T00:00:00",
        "end": "2026-07-01T03:00:00",
    }
    parsed = parse_backfill_conf(conf)

    assert parsed["backfill_type"] == "hourly"
    assert parsed["start"] == "2026-07-01 00:00:00"
    assert parsed["end"] == "2026-07-01 03:00:00"
    assert parsed["start_date"] == "2026-07-01"
    assert parsed["end_date"] == "2026-07-01"


def test_parse_daily_config_valid():
    """
    Test parsing valid daily backfill configuration.
    """
    conf = {
        "backfill_type": "daily",
        "start": "2026-07-01",
        "end": "2026-07-07",
    }
    parsed = parse_backfill_conf(conf)

    assert parsed["backfill_type"] == "daily"
    assert parsed["start_date"] == "2026-07-01"
    assert parsed["end_date"] == "2026-07-07"


def test_generate_daily_dates_inclusive():
    """
    Test generate_daily_dates generates inclusive date list.
    """
    dates = generate_daily_dates("2026-07-01", "2026-07-03")

    assert dates == [
        "2026-07-01",
        "2026-07-02",
        "2026-07-03",
    ]


def test_generate_hourly_windows_half_open():
    """
    Test generate_hourly_windows generates half-open [start, end) hourly windows.
    """
    start_dt = pendulum.datetime(2026, 7, 1, 0, 0, 0, tz="UTC")
    end_dt = pendulum.datetime(2026, 7, 1, 3, 0, 0, tz="UTC")

    windows = generate_hourly_windows(start_dt, end_dt)

    assert len(windows) == 3
    assert windows[0] == ("2026-07-01 00:00:00", "2026-07-01 01:00:00")
    assert windows[1] == ("2026-07-01 01:00:00", "2026-07-01 02:00:00")
    assert windows[2] == ("2026-07-01 02:00:00", "2026-07-01 03:00:00")


def test_parse_backfill_conf_invalid_type():
    """
    Test parse_backfill_conf raises ValueError for invalid backfill_type.
    """
    conf = {
        "backfill_type": "wrong",
        "start": "2026-07-01T00:00:00",
        "end": "2026-07-01T03:00:00",
    }
    with pytest.raises(ValueError, match="Invalid backfill_type"):
        parse_backfill_conf(conf)


def test_parse_backfill_conf_missing_start_or_end():
    """
    Test parse_backfill_conf raises ValueError when start or end is missing.
    """
    conf_no_start = {
        "backfill_type": "hourly",
        "end": "2026-07-01T03:00:00",
    }
    with pytest.raises(ValueError, match="start"):
        parse_backfill_conf(conf_no_start)

    conf_no_end = {
        "backfill_type": "hourly",
        "start": "2026-07-01T00:00:00",
    }
    with pytest.raises(ValueError, match="end"):
        parse_backfill_conf(conf_no_end)


def test_parse_backfill_conf_start_greater_or_equal_end():
    """
    Test parse_backfill_conf raises ValueError when start >= end.
    """
    conf_equal = {
        "backfill_type": "hourly",
        "start": "2026-07-01T03:00:00",
        "end": "2026-07-01T03:00:00",
    }
    with pytest.raises(ValueError, match="(?:must be earlier than|cannot be greater than)"):
        parse_backfill_conf(conf_equal)

    conf_greater = {
        "backfill_type": "daily",
        "start": "2026-07-05",
        "end": "2026-07-01",
    }
    with pytest.raises(ValueError, match="(?:must be earlier than|cannot be greater than)"):
        parse_backfill_conf(conf_greater)


def test_parse_backfill_conf_exceeds_max_hourly_days():
    """
    Test parse_backfill_conf raises ValueError when hourly range exceeds 31 days.
    """
    conf = {
        "backfill_type": "hourly",
        "start": "2026-01-01T00:00:00",
        "end": "2026-03-01T00:00:00",
    }
    with pytest.raises(ValueError, match="(?:exceeds maximum allowed limit of 31 days|must not exceed 31 days)"):
        parse_backfill_conf(conf)


def test_parse_backfill_conf_exceeds_max_daily_days():
    """
    Test parse_backfill_conf raises ValueError when daily range exceeds 366 days.
    """
    conf = {
        "backfill_type": "daily",
        "start": "2024-01-01",
        "end": "2026-01-01",
    }
    with pytest.raises(ValueError, match="(?:exceeds maximum allowed limit of 366|exceeds the maximum allowed limit of 366)"):
        parse_backfill_conf(conf)
