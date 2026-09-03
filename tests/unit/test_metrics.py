"""
Unit tests for FastAPI Prometheus Metrics integration & Route Normalization.
Supports standalone host execution with fallback dependency mocks.
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

# Provide mock fallbacks if dependencies are missing in host environment
for mod in [
    "fastapi",
    "prometheus_client",
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

from api.metrics import normalize_route_path, update_freshness_prometheus_metrics


class TestMetricsIntegration(unittest.TestCase):
    def test_normalize_route_path(self):
        """Test URL route normalization to protect against high cardinality labels."""
        self.assertEqual(normalize_route_path("/"), "/")
        self.assertEqual(normalize_route_path("/metrics"), "/metrics")
        self.assertEqual(normalize_route_path("/docs"), "/docs")

        # Station routes
        self.assertEqual(
            normalize_route_path("/api/v1/stations/31200"),
            "/api/v1/stations/{station_id}",
        )
        self.assertEqual(
            normalize_route_path("/api/v1/stations/station_xyz/history"),
            "/api/v1/stations/{station_id}/history",
        )
        self.assertEqual(
            normalize_route_path("/api/v1/stations/31200/daily"),
            "/api/v1/stations/{station_id}/daily",
        )

        # Region routes
        self.assertEqual(
            normalize_route_path("/api/v1/regions/r_123"),
            "/api/v1/regions/{region_id}",
        )
        self.assertEqual(
            normalize_route_path("/api/v1/regions/r_123/history"),
            "/api/v1/regions/{region_id}/history",
        )

    @patch("api.metrics.fetch_one")
    @patch("api.metrics.get_data_freshness_summary")
    def test_update_freshness_prometheus_metrics(self, mock_get_freshness, mock_fetch_one):
        """Test updating Prometheus gauges from Data Freshness service data."""
        mock_get_freshness.return_value = {
            "station_status_lag_minutes": 12.5,
            "hourly_mart_lag_minutes": 45.0,
            "latest_daily_summary_date": "2026-09-03",
            "latest_pipeline_health_status": "HEALTHY",
            "status": "HEALTHY",
            "latest_successful_dag_runs": [
                {"dag_id": "station_status_snapshot_dag", "lag_minutes": 10.0},
                {"dag_id": "hourly_mart_build_dag", "lag_minutes": 40.0},
            ],
        }

        mock_fetch_one.return_value = {
            "failed_cnt": 0,
            "warning_cnt": 1,
            "self_healed_cnt": 2,
        }

        update_freshness_prometheus_metrics()

        mock_get_freshness.assert_called_once()
        mock_fetch_one.assert_called_once()


if __name__ == "__main__":
    unittest.main()
