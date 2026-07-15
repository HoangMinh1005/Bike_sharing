import json
import uuid
from src.common.db import fetch_one, execute_sql
from src.load.raw_loader import load_gbfs_raw, compute_payload_hash

def test_load_gbfs_raw_insert_record_successfully():
    """
    Integration test to verify that load_gbfs_raw successfully inserts a record
    with proper fields, UTC time, and payload hash.
    """
    batch_id = f"test-raw-loader-{uuid.uuid4()}"
    feed_name = "test_system_information"
    language = "en"

    mock_payload = {
        "last_updated": 1713000000,
        "ttl": 300,
        "data": {
            "system_id": "test_system",
            "name": "Test System"
        }
    }

    try:
        # 1. Execute load_gbfs_raw
        row_count = load_gbfs_raw(
            feed_name=feed_name,
            payload=mock_payload,
            batch_id=batch_id,
            language=language
        )

        # 2. Verify row count returned is 1
        assert row_count == 1

        # 3. Query the database to retrieve the record
        row = fetch_one(
            "SELECT * FROM raw.gbfs_feed_snapshots WHERE batch_id = :batch_id AND feed_name = :feed_name",
            {"batch_id": batch_id, "feed_name": feed_name}
        )

        # 4. Verify all fields of the retrieved record
        assert row is not None
        assert row["batch_id"] == batch_id
        assert row["feed_name"] == feed_name
        assert row["language"] == language
        assert row["ttl"] == 300
        assert row["fetched_at"] is not None
        assert row["source_last_updated"] is not None

        # Verify hash match
        expected_hash = compute_payload_hash(mock_payload)
        assert row["payload_hash"] == expected_hash

        # Extract raw_payload dict safely
        raw_payload_dict = (
            json.loads(row["raw_payload"]) 
            if isinstance(row["raw_payload"], str) 
            else row["raw_payload"]
        )

        assert raw_payload_dict["data"]["system_id"] == "test_system"
        assert raw_payload_dict["data"]["name"] == "Test System"

    finally:
        # 5. Clean up the database test record
        execute_sql(
            "DELETE FROM raw.gbfs_feed_snapshots WHERE batch_id = :batch_id",
            {"batch_id": batch_id}
        )
