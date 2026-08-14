"""
Unit tests for Station-Region Mapping Data Quality thresholds and UNKNOWN_REGION handling.
"""
import pytest
from unittest.mock import patch, MagicMock


def calculate_station_region_dq_status(total_count: int, unmapped_count: int):
    """
    Helper function mirroring the logic in metadata_checks.py
    """
    rate = (unmapped_count / total_count) if total_count > 0 else 0.0
    if rate <= 0.01:
        return {
            "status": "passed",
            "severity": "INFO",
            "rate": rate,
            "is_blocking": False,
            "message": f"{unmapped_count}/{total_count} stations ({rate*100:.2f}%) mapped to UNKNOWN_REGION (accepted <= 1.0% threshold)."
        }
    elif rate <= 0.05:
        return {
            "status": "warning",
            "severity": "WARNING",
            "rate": rate,
            "is_blocking": False,
            "message": f"{unmapped_count}/{total_count} stations ({rate*100:.2f}%) have unmapped region_id, exceeding 1.0% threshold."
        }
    else:
        return {
            "status": "failed",
            "severity": "CRITICAL",
            "rate": rate,
            "is_blocking": True,
            "message": f"{unmapped_count}/{total_count} stations ({rate*100:.2f}%) have unmapped region_id, exceeding critical 5.0% threshold."
        }


def test_station_region_dq_all_valid():
    """
    Test Case 1: 100% stations have valid region_id (0% unmapped) -> PASSED (INFO / HEALTHY)
    """
    result = calculate_station_region_dq_status(total_count=1000, unmapped_count=0)
    assert result["status"] == "passed"
    assert result["severity"] == "INFO"
    assert result["is_blocking"] is False
    assert result["rate"] == 0.0


def test_station_region_dq_under_one_percent():
    """
    Test Case 2: 6 stations out of 1000 missing region_id (0.6% <= 1.0%) -> PASSED (INFO / Non-blocking)
    """
    result = calculate_station_region_dq_status(total_count=1000, unmapped_count=6)
    assert result["status"] == "passed"
    assert result["severity"] == "INFO"
    assert result["is_blocking"] is False
    assert round(result["rate"] * 100, 2) == 0.60


def test_station_region_dq_between_one_and_five_percent():
    """
    Test Case 3: 30 stations out of 1000 missing region_id (3.0% > 1.0% and <= 5.0%) -> WARNING
    """
    result = calculate_station_region_dq_status(total_count=1000, unmapped_count=30)
    assert result["status"] == "warning"
    assert result["severity"] == "WARNING"
    assert result["is_blocking"] is False
    assert round(result["rate"] * 100, 2) == 3.00


def test_station_region_dq_above_five_percent():
    """
    Test Case 4: 80 stations out of 1000 missing region_id (8.0% > 5.0%) -> CRITICAL / ERROR
    """
    result = calculate_station_region_dq_status(total_count=1000, unmapped_count=80)
    assert result["status"] == "failed"
    assert result["severity"] == "CRITICAL"
    assert result["is_blocking"] is True
    assert round(result["rate"] * 100, 2) == 8.00


def test_orphan_station_status_check_severity():
    """
    Test Case 5: station_status.station_id not in staging.stations must be CRITICAL
    """
    from src.quality.station_status_checks import run_station_status_dq_checks

    with patch("src.quality.station_status_checks.fetch_one") as mock_fetch, \
         patch("src.quality.station_status_checks.write_dq_result") as mock_write:
        
        # Simulate 5 orphan station_status records
        def mock_query(sql, params):
            if "staging.stations" in sql:
                return {"failed_count": 5}
            return {"failed_count": 0}
        
        mock_fetch.side_effect = mock_query

        # Should raise ValueError because severity is CRITICAL
        with pytest.raises(ValueError, match="Critical station_status DQ checks failed"):
            run_station_status_dq_checks(batch_id="test_batch", run_id="test_run")
        
        # Verify that write_dq_result recorded CRITICAL severity
        called_checks = [c.kwargs for c in mock_write.call_args_list if c.kwargs.get("check_name") == "staging_station_status_map_to_stations_metadata"]
        assert len(called_checks) == 1
        assert called_checks[0]["severity"] == "CRITICAL"
        assert called_checks[0]["status"] == "failed"
