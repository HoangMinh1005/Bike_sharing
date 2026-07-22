import time
from typing import Any, Dict

import requests

from src.common.logger import get_logger

logger = get_logger(__name__)


class WeatherClient:
    """
    Client for Open-Meteo Forecast API.

    This client fetches hourly weather data for a given coordinate.
    It is designed for MVP enrichment pipeline and does not require an API key.
    """

    DEFAULT_HOURLY_FIELDS = [
        "temperature_2m",
        "relative_humidity_2m",
        "precipitation",
        "wind_speed_10m",
        "weather_code",
    ]

    def __init__(
        self,
        base_url: str,
        max_retries: int = 3,
        retry_delay: int = 2,
        timeout: int = 30,
    ):
        """
        Initialize the Weather client.

        Args:
            base_url: Open-Meteo Forecast API base URL,
                e.g. https://api.open-meteo.com/v1/forecast
            max_retries: Maximum retry attempts for network/5xx errors.
            retry_delay: Delay in seconds between retry attempts.
            timeout: Request timeout in seconds.
        """
        if not base_url or not isinstance(base_url, str):
            raise ValueError("Weather API base_url must be a non-empty string")

        if max_retries <= 0:
            raise ValueError("max_retries must be greater than 0")

        if retry_delay < 0:
            raise ValueError("retry_delay must be greater than or equal to 0")

        if timeout <= 0:
            raise ValueError("timeout must be greater than 0")

        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout

    def fetch_hourly_weather(
        self,
        latitude: float,
        longitude: float,
        timezone: str,
        lookback_hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Fetch hourly weather from Open-Meteo for the specified location.

        Uses the `past_hours` parameter to retrieve recent hourly weather data.

        Args:
            latitude: Location latitude.
            longitude: Location longitude.
            timezone: Timezone name, e.g. America/New_York.
            lookback_hours: Number of past hours to fetch.

        Returns:
            Open-Meteo JSON payload as dictionary.

        Raises:
            ValueError: If input or response payload is invalid.
            requests.exceptions.RequestException: If the request fails.
        """
        self._validate_request_inputs(
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            lookback_hours=lookback_hours,
        )

        hourly_fields = ",".join(self.DEFAULT_HOURLY_FIELDS)

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone,
            "hourly": hourly_fields,
            "past_hours": lookback_hours,
        }

        logger.info(
            f"Calling Weather API. "
            f"base_url={self.base_url}, lat={latitude}, lon={longitude}, "
            f"timezone={timezone}, lookback_hours={lookback_hours}"
        )

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.get(
                    self.base_url,
                    params=params,
                    timeout=self.timeout,
                )

                if 400 <= response.status_code < 500:
                    logger.error(
                        f"Client error from Weather API. "
                        f"status={response.status_code}, base_url={self.base_url}"
                    )
                    response.raise_for_status()

                if 500 <= response.status_code < 600:
                    logger.warning(
                        f"Weather API server error. "
                        f"attempt={attempt}/{self.max_retries}, "
                        f"status={response.status_code}"
                    )

                    if attempt == self.max_retries:
                        response.raise_for_status()

                    time.sleep(self.retry_delay)
                    continue

                response.raise_for_status()

                payload = response.json()
                self._validate_response_payload(payload)

                logger.info("Successfully fetched hourly weather data.")
                return payload

            except requests.exceptions.HTTPError as e:
                status_code = (
                    e.response.status_code
                    if e.response is not None
                    else None
                )

                if status_code is not None and 400 <= status_code < 500:
                    logger.error(
                        f"HTTP client error from Weather API. "
                        f"status={status_code}. Aborting retries."
                    )
                    raise

                logger.warning(
                    f"Weather API HTTP error. "
                    f"attempt={attempt}/{self.max_retries}, "
                    f"status={status_code}, error={e}"
                )

                if attempt == self.max_retries:
                    raise

                time.sleep(self.retry_delay)

            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"Weather API request error. "
                    f"attempt={attempt}/{self.max_retries}, error={e}"
                )

                if attempt == self.max_retries:
                    raise

                time.sleep(self.retry_delay)

            except ValueError:
                # Invalid payload or invalid request input should not be retried.
                raise

        raise RuntimeError("Failed to fetch weather data after maximum retries")

    @staticmethod
    def _validate_request_inputs(
        latitude: float,
        longitude: float,
        timezone: str,
        lookback_hours: int,
    ) -> None:
        """
        Validate request inputs before calling the API.
        """
        if not isinstance(latitude, (int, float)) or not -90 <= latitude <= 90:
            raise ValueError("latitude must be a number between -90 and 90")

        if not isinstance(longitude, (int, float)) or not -180 <= longitude <= 180:
            raise ValueError("longitude must be a number between -180 and 180")

        if not timezone or not isinstance(timezone, str):
            raise ValueError("timezone must be a non-empty string")

        if not isinstance(lookback_hours, int) or lookback_hours <= 0:
            raise ValueError("lookback_hours must be a positive integer")

    @staticmethod
    def _validate_response_payload(payload: Dict[str, Any]) -> None:
        """
        Validate the basic Open-Meteo hourly response structure.
        """
        if not isinstance(payload, dict):
            raise ValueError("Invalid Weather API response: payload must be a dict")

        hourly = payload.get("hourly")

        if not isinstance(hourly, dict):
            raise ValueError(
                "Invalid Weather API response: 'hourly' must be an object"
            )

        hourly_time = hourly.get("time")

        if not isinstance(hourly_time, list) or len(hourly_time) == 0:
            raise ValueError(
                "Invalid Weather API response: 'hourly.time' is missing or empty"
            )