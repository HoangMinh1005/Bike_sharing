import uuid
import pytest
from src.extract.gbfs_client import GBFSClient
from src.load.raw_loader import load_gbfs_raw
from src.common.db import fetch_one, execute_sql

def test_metadata_pipeline_integration():
    """
    Integration test for extraction and DB loading of raw metadata.
    """
    batch_id = f"test-batch-{uuid.uuid4()}"
    feed_name = "test_system_information"
    
    mock_payload = {
        "last_updated": 1713000000,
        "ttl": 300,
        "data": {
            "system_id": "test_system",
            "name": "Test System"
        }
    }
    
    try:
        # Load raw data using raw_loader
        row_count = load_gbfs_raw(
            feed_name=feed_name,
            payload=mock_payload,
            batch_id=batch_id,
            language="en"
        )
        
        # Verify row count returned is 1
        assert row_count == 1
        
        # Query database to verify it exists
        row = fetch_one(
            "SELECT * FROM raw.gbfs_feed_snapshots WHERE batch_id = :batch_id AND feed_name = :feed_name",
            {"batch_id": batch_id, "feed_name": feed_name}
        )
        
        assert row is not None
        assert row["ttl"] == 300
        assert row["raw_payload"]["data"]["system_id"] == "test_system"
        
    finally:
        # Clean up database test record
        execute_sql(
            "DELETE FROM raw.gbfs_feed_snapshots WHERE batch_id = :batch_id",
            {"batch_id": batch_id}
        )
