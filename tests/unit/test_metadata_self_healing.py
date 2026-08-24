"""
Unit tests for Controlled Metadata Drift Self-Healing mechanism.
Supports standalone host execution with fallback dependency mocks.
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

# Provide mock fallbacks if dependencies are missing in host environment
for mod in [
    "sqlalchemy",
    "sqlalchemy.engine",
    "pendulum",
    "pydantic_settings",
    "pydantic",
    "requests",
    "airflow",
    "airflow.decorators",
    "airflow.operators",
    "airflow.operators.python",
]:
    if mod not in sys.modules:
        try:
            __import__(mod)
        except ImportError:
            sys.modules[mod] = MagicMock()

from src.quality.station_status_checks import (
    AUTO_REFRESH_MAX_UNMAPPED_COUNT,
    AUTO_REFRESH_MAX_UNMAPPED_RATE,
    run_station_status_dq_checks,
)


class TestMetadataSelfHealing(unittest.TestCase):
    @patch("src.quality.station_status_checks.write_dq_result")
    @patch("src.quality.station_status_checks.fetch_all")
    @patch("src.quality.station_status_checks.fetch_one")
    @patch("src.quality.station_status_checks.refresh_gbfs_station_metadata")
    def test_mapping_check_pass_normal(
        self, mock_refresh, mock_fetch_one, mock_fetch_all, mock_write_dq
    ):
        """Case 1: All stations mapped (unmapped_count = 0). Normal pass, no refresh called."""
        mock_fetch_one.return_value = {"cnt": 100, "failed_count": 0, "duplicate_count": 0}
        mock_fetch_all.return_value = []

        run_station_status_dq_checks(run_id="test_run_1", batch_id="test_batch_1")

        mock_refresh.assert_not_called()

        mapping_calls = [
            call for call in mock_write_dq.call_args_list
            if call.kwargs.get("check_name") == "staging_station_status_map_to_stations_metadata"
        ]
        self.assertEqual(len(mapping_calls), 1)
        self.assertEqual(mapping_calls[0].kwargs.get("status"), "passed")
        self.assertEqual(mapping_calls[0].kwargs.get("failed_count"), 0)

    @patch("src.quality.station_status_checks.write_dq_result")
    @patch("src.quality.station_status_checks.fetch_all")
    @patch("src.quality.station_status_checks.fetch_one")
    @patch("src.quality.station_status_checks.refresh_gbfs_station_metadata")
    def test_mapping_check_self_heal_success(
        self, mock_refresh, mock_fetch_one, mock_fetch_all, mock_write_dq
    ):
        """Case 2: 1 unmapped station (< threshold). Refresh succeeds, recheck passes, no pipeline fail."""
        mock_fetch_one.return_value = {"cnt": 1000, "failed_count": 0, "duplicate_count": 0}
        mock_refresh.return_value = {"transformed_stations": 1}

        # First fetch_all (initial check): 1 unmapped station
        # Second fetch_all (recheck after refresh): 0 unmapped stations
        mock_fetch_all.side_effect = [
            [{"station_id": "new_station_999"}],
            [],
        ]

        run_station_status_dq_checks(run_id="test_run_2", batch_id="test_batch_2")

        mock_refresh.assert_called_once_with(
            batch_id="test_batch_2",
            reason="metadata_drift_self_healing",
        )

        mapping_calls = [
            call for call in mock_write_dq.call_args_list
            if call.kwargs.get("check_name") == "staging_station_status_map_to_stations_metadata"
        ]
        self.assertEqual(len(mapping_calls), 1)
        self.assertEqual(mapping_calls[0].kwargs.get("status"), "passed")
        self.assertIn("Self-healed", mapping_calls[0].kwargs.get("message"))

    @patch("src.quality.station_status_checks.write_dq_result")
    @patch("src.quality.station_status_checks.fetch_all")
    @patch("src.quality.station_status_checks.fetch_one")
    @patch("src.quality.station_status_checks.refresh_gbfs_station_metadata")
    def test_mapping_check_exceeds_threshold(
        self, mock_refresh, mock_fetch_one, mock_fetch_all, mock_write_dq
    ):
        """Case 3: Unmapped count exceeds threshold (10 unmapped stations). Auto self-heal skipped, fails pipeline."""
        mock_fetch_one.return_value = {"cnt": 100, "failed_count": 0, "duplicate_count": 0}
        mock_fetch_all.return_value = [{"station_id": f"unmapped_{i}"} for i in range(10)]

        with self.assertRaises(ValueError):
            run_station_status_dq_checks(run_id="test_run_3", batch_id="test_batch_3")

        mock_refresh.assert_not_called()

        mapping_calls = [
            call for call in mock_write_dq.call_args_list
            if call.kwargs.get("check_name") == "staging_station_status_map_to_stations_metadata"
        ]
        self.assertEqual(len(mapping_calls), 1)
        self.assertEqual(mapping_calls[0].kwargs.get("status"), "failed")
        self.assertEqual(mapping_calls[0].kwargs.get("failed_count"), 10)

    @patch("src.quality.station_status_checks.write_dq_result")
    @patch("src.quality.station_status_checks.fetch_all")
    @patch("src.quality.station_status_checks.fetch_one")
    @patch("src.quality.station_status_checks.refresh_gbfs_station_metadata")
    def test_mapping_check_refresh_fails(
        self, mock_refresh, mock_fetch_one, mock_fetch_all, mock_write_dq
    ):
        """Case 4: Refresh metadata raises an exception. DQ check fails and raises ValueError."""
        mock_fetch_one.return_value = {"cnt": 1000, "failed_count": 0, "duplicate_count": 0}
        mock_fetch_all.return_value = [{"station_id": "new_station_888"}]
        mock_refresh.side_effect = RuntimeError("GBFS API connection timeout")

        with self.assertRaises(ValueError):
            run_station_status_dq_checks(run_id="test_run_4", batch_id="test_batch_4")

        mock_refresh.assert_called_once()

        mapping_calls = [
            call for call in mock_write_dq.call_args_list
            if call.kwargs.get("check_name") == "staging_station_status_map_to_stations_metadata"
        ]
        self.assertEqual(len(mapping_calls), 1)
        self.assertEqual(mapping_calls[0].kwargs.get("status"), "failed")

    def test_dag_import_regression(self):
        """Case 5: Regression test to ensure Airflow DAGs parse cleanly."""
        import dags.gbfs_metadata_daily_dag as metadata_dag
        import dags.station_status_snapshot_dag as status_dag

        self.assertIsNotNone(metadata_dag.gbfs_metadata_daily_dag)
        self.assertIsNotNone(status_dag.station_status_snapshot_dag)


if __name__ == "__main__":
    unittest.main()
