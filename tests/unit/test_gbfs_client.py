import pytest
from unittest.mock import patch, MagicMock
import requests
from src.extract.gbfs_client import GBFSClient

def test_fetch_feed_success():
    """
    Test successful feed retrieval.
    """
    client = GBFSClient("https://gbfs.example.com")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "last_updated": 1600000000, 
        "ttl": 60, 
        "data": {"stations": []}
    }
    
    with patch("requests.get", return_value=mock_response) as mock_get:
        payload = client.fetch_feed("system_information")
        mock_get.assert_called_once_with("https://gbfs.example.com/system_information.json", timeout=30)
        assert payload["data"] == {"stations": []}

def test_fetch_feed_missing_data():
    """
    Test ValueError is raised when 'data' is missing from the response.
    """
    client = GBFSClient("https://gbfs.example.com")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"last_updated": 1600000000, "ttl": 60}  # missing 'data'
    
    with patch("requests.get", return_value=mock_response):
        with pytest.raises(ValueError, match="data' field is missing"):
            client.fetch_feed("system_information")

def test_fetch_feed_retry_on_5xx():
    """
    Test retry logic succeeds on subsequent attempts if a 5xx code is encountered.
    """
    client = GBFSClient("https://gbfs.example.com")
    
    mock_response_500 = MagicMock()
    mock_response_500.status_code = 500
    
    mock_response_200 = MagicMock()
    mock_response_200.status_code = 200
    mock_response_200.json.return_value = {"data": {}}
    
    # Mock calls: first returns 500, second returns 200
    with patch("requests.get", side_effect=[mock_response_500, mock_response_200]) as mock_get:
        with patch("time.sleep") as mock_sleep:  # Mock sleep to run tests immediately
            payload = client.fetch_feed("system_information")
            assert mock_get.call_count == 2
            assert payload == {"data": {}}
            mock_sleep.assert_called_once()
