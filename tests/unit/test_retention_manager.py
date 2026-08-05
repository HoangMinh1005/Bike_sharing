from datetime import datetime
import copy
import pendulum
import pytest

from src.cleanup.retention_manager import (
    RETENTION_POLICIES,
    _is_allowed_retention_target,
    _normalize_reference_time,
    _validate_retention_policy,
    get_retention_policies,
)


def test_get_retention_policies_returns_copy():
    """
    Test get_retention_policies returns a deep copy and global RETENTION_POLICIES is immutable.
    """
    policies_copy = get_retention_policies()
    assert len(policies_copy) > 0

    # Modify the returned list
    original_days = policies_copy[0]["retention_days"]
    policies_copy[0]["retention_days"] = 9999

    # Retrieve fresh policies and verify original is unchanged
    fresh_policies = get_retention_policies()
    assert fresh_policies[0]["retention_days"] == original_days
    assert RETENTION_POLICIES[0]["retention_days"] == original_days


def test_valid_retention_target():
    """
    Test _is_allowed_retention_target returns True for exact whitelisted targets.
    """
    assert _is_allowed_retention_target("raw.gbfs_feed_snapshots", "fetched_at", 30) is True
    assert _is_allowed_retention_target("raw.calendar", "loaded_at", 400) is True


def test_invalid_retention_target():
    """
    Test _is_allowed_retention_target returns False for non-whitelisted target/columns.
    """
    # Non-existent table
    assert _is_allowed_retention_target("public.users", "created_at", 30) is False
    # Non-existent column on valid table
    assert _is_allowed_retention_target("raw.gbfs_feed_snapshots", "id", 30) is False
    # Wrong retention_days for valid table
    assert _is_allowed_retention_target("raw.gbfs_feed_snapshots", "fetched_at", 999) is False


def test_invalid_table_name_format():
    """
    Test _validate_retention_policy raises ValueError for dangerous/invalid table name formats.
    """
    invalid_policy = {
        "table_name": "raw;DROP TABLE x",
        "timestamp_column": "fetched_at",
        "retention_days": 30,
        "enabled": True,
    }
    with pytest.raises(ValueError, match="Invalid table_name"):
        _validate_retention_policy(invalid_policy)


def test_invalid_timestamp_column_format():
    """
    Test _validate_retention_policy raises ValueError for invalid column name formats.
    """
    invalid_policy = {
        "table_name": "raw.gbfs_feed_snapshots",
        "timestamp_column": "fetched_at;DROP",
        "retention_days": 30,
        "enabled": True,
    }
    with pytest.raises(ValueError, match="Invalid timestamp_column"):
        _validate_retention_policy(invalid_policy)


def test_retention_days_invalid():
    """
    Test _validate_retention_policy raises ValueError when retention_days <= 0 or not an int.
    """
    policy_zero = {
        "table_name": "raw.gbfs_feed_snapshots",
        "timestamp_column": "fetched_at",
        "retention_days": 0,
        "enabled": True,
    }
    with pytest.raises(ValueError, match="retention_days"):
        _validate_retention_policy(policy_zero)

    policy_negative = {
        "table_name": "raw.gbfs_feed_snapshots",
        "timestamp_column": "fetched_at",
        "retention_days": -10,
        "enabled": True,
    }
    with pytest.raises(ValueError, match="retention_days"):
        _validate_retention_policy(policy_negative)


def test_enabled_flag_invalid():
    """
    Test _validate_retention_policy raises ValueError when enabled is not a boolean.
    """
    invalid_policy = {
        "table_name": "raw.gbfs_feed_snapshots",
        "timestamp_column": "fetched_at",
        "retention_days": 30,
        "enabled": "yes",
    }
    with pytest.raises(ValueError, match="enabled"):
        _validate_retention_policy(invalid_policy)


def test_normalize_reference_time():
    """
    Test _normalize_reference_time parses None, ISO string, datetime, and pendulum DateTime to UTC.
    """
    # 1. None -> current UTC
    ref_none = _normalize_reference_time(None)
    assert isinstance(ref_none, pendulum.DateTime)
    assert ref_none.tzinfo.name == "UTC"

    # 2. ISO string -> UTC pendulum
    ref_str = _normalize_reference_time("2026-07-15T12:00:00Z")
    assert isinstance(ref_str, pendulum.DateTime)
    assert ref_str.year == 2026
    assert ref_str.month == 7
    assert ref_str.day == 15
    assert ref_str.tzinfo.name == "UTC"

    # 3. Naive datetime -> interpret UTC pendulum
    naive_dt = datetime(2026, 7, 15, 12, 0, 0)
    ref_naive = _normalize_reference_time(naive_dt)
    assert isinstance(ref_naive, pendulum.DateTime)
    assert ref_naive.tzinfo.name == "UTC"
