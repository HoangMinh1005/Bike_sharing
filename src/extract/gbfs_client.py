import time
from typing import Any, Dict

import requests

from src.common.logger import get_logger

logger = get_logger(__name__)


class GBFSClient:
    """
    Client for fetching standard GBFS feeds.
    """

    def __init__(self, base_url: str):
        """
        Initialize the GBFS client.

        :param base_url: Base URL of the GBFS API,
                         e.g. https://gbfs.lyft.com/gbfs/2.3/bkn/en
        """
        self.base_url = base_url.rstrip("/")

    def fetch_feed(self, feed_name: str) -> Dict[str, Any]:
        """
        Fetch a specific GBFS feed by name and return its parsed JSON dictionary.

        Retries only on network errors and HTTP 5xx errors.
        Raises immediately on HTTP 4xx errors.
        """
        url = f"{self.base_url}/{feed_name}.json"

        max_retries = 3
        retry_delay = 2
        timeout = 30

        logger.info(f"Calling GBFS feed URL: {url}")

        for attempt in range(1, max_retries + 1):
            try:
                response = requests.get(url, timeout=timeout)

                # 4xx usually means the request is wrong.
                # Retrying usually does not help.
                if 400 <= response.status_code < 500:
                    logger.error(
                        f"Client error while fetching feed '{feed_name}': "
                        f"status={response.status_code}, url={url}"
                    )
                    response.raise_for_status()

                # 5xx usually means temporary server-side error.
                # These errors are worth retrying.
                if 500 <= response.status_code < 600:
                    logger.warning(
                        f"Attempt {attempt}/{max_retries} failed with "
                        f"server status {response.status_code}."
                    )

                    if attempt == max_retries:
                        response.raise_for_status()

                    time.sleep(retry_delay)
                    continue

                response.raise_for_status()

                payload = response.json()

                if "data" not in payload:
                    raise ValueError(
                        f"Invalid GBFS response from {url}: 'data' field is missing."
                    )

                logger.info(f"Successfully fetched GBFS feed: {feed_name}")
                return payload

            except requests.exceptions.HTTPError as e:
                error_response = e.response
                status_code = error_response.status_code if error_response is not None else None

                if status_code is not None and 400 <= status_code < 500:
                    logger.error(
                        f"HTTP Client Error {status_code} while fetching "
                        f"feed '{feed_name}': {e} - Aborting retries."
                    )
                    raise

                logger.warning(
                    f"Attempt {attempt}/{max_retries} failed with server status "
                    f"{status_code}: {e}"
                )

                if attempt == max_retries:
                    raise

                time.sleep(retry_delay)

            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"Attempt {attempt}/{max_retries} failed due to network error "
                    f"while fetching feed '{feed_name}': {e}"
                )

                if attempt == max_retries:
                    logger.error(
                        f"Failed to fetch feed '{feed_name}' after "
                        f"{max_retries} attempts."
                    )
                    raise

                time.sleep(retry_delay)

            except ValueError as e:
                logger.error(f"Invalid JSON or invalid GBFS payload for feed '{feed_name}': {e}")
                raise

        raise RuntimeError(f"Unexpected exit of retry loop for feed '{feed_name}'")