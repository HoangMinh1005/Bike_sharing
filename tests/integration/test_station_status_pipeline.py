import json
import uuid
import pytest

from src.common.db import execute_sql, fetch_one, fetch_all
from src.load.station_status_raw_loader import load_station_status_raw
from src.transform.station_status_transformer import (
    transform_station_status,
    transform_station_vehicle_type_status,
)
from src.quality.station_status_checks import run_station_status_dq_checks


@pytest.fixture
def clean_test_batches():
    batches = []

    yield batches

    # Teardown: Delete all generated batches from raw and staging tables
    for batch_id in batches:
        execute_sql(
            "DELETE FROM raw.station_status_snapshots WHERE batch_id = :batch_id",
            {"batch_id": batch_id},
        )
        execute_sql(
            "DELETE FROM staging.station_status WHERE batch_id = :batch_id",
            {"batch_id": batch_id},
        )
        execute_sql(
            "DELETE FROM staging.station_vehicle_type_status WHERE batch_id = :batch_id",
            {"batch_id": batch_id},
        )
        execute_sql(
            "DELETE FROM etl_metadata.dq_results WHERE run_id = :batch_id",
            {"batch_id": batch_id},
        )
        execute_sql(
            "DELETE FROM etl_metadata.rejected_records WHERE run_id = :batch_id",
            {"batch_id": batch_id},
        )


def test_load_station_status_raw_and_idempotency(clean_test_batches):
    batch_id = f"test-ss-raw-{uuid.uuid4()}"
    clean_test_batches.append(batch_id)

    mock_payload = {
        "last_updated": 1713000000,
        "ttl": 60,
        "data": {
            "stations": [
                {
                    "station_id": "station_1",
                    "num_bikes_available": 5,
                    "num_docks_available": 10,
                    "is_installed": True,
                    "is_renting": True,
                    "is_returning": True,
                    "last_reported": 1713000000,
                    "vehicle_types_available": [
                        {"vehicle_type_id": "classic", "count": 5}
                    ]
                },
                {
                    "station_id": "station_2",
                    "num_bikes_available": 3,
                    "num_docks_available": 12,
                    "is_installed": True,
                    "is_renting": True,
                    "is_returning": True,
                    "last_reported": 1713000000,
                },
                {
                    # Invalid station (missing station_id)
                    "num_bikes_available": 1,
                    "num_docks_available": 20,
                }
            ]
        }
    }

    # 1. Load raw snapshots
    row_count = load_station_status_raw(
        payload=mock_payload,
        batch_id=batch_id,
        run_id=batch_id,
    )

    # Should successfully load 2 stations (since 3rd is missing station_id)
    assert row_count == 2

    # Verify rejected record for 3rd station was recorded
    rejected = fetch_one(
        "SELECT COUNT(*) as count FROM etl_metadata.rejected_records WHERE run_id = :batch_id",
        {"batch_id": batch_id}
    )
    assert rejected["count"] == 1

    # Verify raw records exist
    raw_records = fetch_all(
        "SELECT * FROM raw.station_status_snapshots WHERE batch_id = :batch_id",
        {"batch_id": batch_id}
    )
    assert len(raw_records) == 2
    
    # 2. Check Idempotency (run again)
    row_count_second = load_station_status_raw(
        payload=mock_payload,
        batch_id=batch_id,
        run_id=batch_id,
    )
    # The upsert logic handles conflicts, returning rows updated/inserted
    assert row_count_second == 2

    # Query DB to make sure total records is still 2 (no duplicates created)
    raw_records_second = fetch_all(
        "SELECT * FROM raw.station_status_snapshots WHERE batch_id = :batch_id",
        {"batch_id": batch_id}
    )
    assert len(raw_records_second) == 2


def test_station_status_transformation(clean_test_batches):
    batch_id = f"test-ss-tx-{uuid.uuid4()}"
    clean_test_batches.append(batch_id)

    mock_payload = {
        "last_updated": 1713000000,
        "ttl": 60,
        "data": {
            "stations": [
                {
                    "station_id": "station_abc",
                    "num_bikes_available": 8,
                    "num_docks_available": 15,
                    "is_installed": True,
                    "is_renting": True,
                    "is_returning": False,
                    "last_reported": 1713000100,
                    "vehicle_types_available": [
                        {"vehicle_type_id": "electric", "count": 3},
                        {"vehicle_type_id": "classic", "count": 5}
                    ]
                }
            ]
        }
    }

    # Load raw
    load_station_status_raw(
        payload=mock_payload,
        batch_id=batch_id,
        run_id=batch_id,
    )

    # Execute transformation
    tx_status = transform_station_status(batch_id)
    tx_vt = transform_station_vehicle_type_status(batch_id)

    assert tx_status == 1
    assert tx_vt == 2

    # Check staging station_status values
    status_row = fetch_one(
        "SELECT * FROM staging.station_status WHERE batch_id = :batch_id",
        {"batch_id": batch_id}
    )
    assert status_row is not None
    assert status_row["station_id"] == "station_abc"
    assert status_row["num_bikes_available"] == 8
    assert status_row["num_docks_available"] == 15
    assert status_row["is_returning"] is False
    assert status_row["is_renting"] is True

    # Check staging vehicle types status
    vt_rows = fetch_all(
        "SELECT * FROM staging.station_vehicle_type_status WHERE batch_id = :batch_id ORDER BY count",
        {"batch_id": batch_id}
    )
    assert len(vt_rows) == 2
    assert vt_rows[0]["vehicle_type_id"] == "electric"
    assert vt_rows[0]["count"] == 3
    assert vt_rows[1]["vehicle_type_id"] == "classic"
    assert vt_rows[1]["count"] == 5


def test_station_status_dq_checks_success_and_failure(clean_test_batches):
    batch_id = f"test-ss-dq-{uuid.uuid4()}"
    clean_test_batches.append(batch_id)

    # 1. Valid data passes DQ checks
    mock_payload = {
        "last_updated": 1713000000,
        "ttl": 60,
        "data": {
            "stations": [
                {
                    "station_id": "station_xyz",
                    "num_bikes_available": 10,
                    "num_docks_available": 20,
                    "is_installed": True,
                    "is_renting": True,
                    "is_returning": True,
                    "last_reported": 1713000000,
                }
            ]
        }
    }

    # Extract/Load and Transform
    load_station_status_raw(mock_payload, batch_id, batch_id)
    transform_station_status(batch_id)

    # Run checks - should pass without raising exceptions
    run_station_status_dq_checks(run_id=batch_id, batch_id=batch_id)

    # 2. Invalid data (negative values) fails DQ checks
    invalid_batch_id = f"test-ss-dq-fail-{uuid.uuid4()}"
    clean_test_batches.append(invalid_batch_id)

    invalid_payload = {
        "last_updated": 1713000000,
        "ttl": 60,
        "data": {
            "stations": [
                {
                    "station_id": "station_err",
                    "num_bikes_available": -5,  # Invalid negative count
                    "num_docks_available": 10,
                    "is_installed": True,
                    "is_renting": True,
                    "is_returning": True,
                    "last_reported": 1713000000,
                }
            ]
        }
    }

    load_station_status_raw(invalid_payload, invalid_batch_id, invalid_batch_id)
    transform_station_status(invalid_batch_id)

    # Expect ValueError for critical DQ failure
    with pytest.raises(ValueError) as excinfo:
        run_station_status_dq_checks(run_id=invalid_batch_id, batch_id=invalid_batch_id)
    
    assert "staging_station_status_bikes_available_non_negative" in str(excinfo.value)
