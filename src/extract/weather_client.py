import time
from typing import Any, Dict
import requests

from src.common.logger import get_logger

logger = get_logger(__name__)


class WeatherClient:
    """
    Client for Open-Meteo API.
    """

    def __init__(self, base_url: str):
        """
        Initialize the Weather client.
        
        :param base_url: Base URL of the weather API,
                         e.g. https://api.open-meteo.com/v1/forecast
        """
        self.base_url = base_url.rstrip("/")

    def fetch_hourly_weather(
        self,
        latitude: float,
        longitude: float,
        timezone: str,
        lookback_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Fetch hourly weather from Open-Meteo for the specified location coordinates.
        Uses past_hours parameters to retrieve historical metrics for lookback window.
        """
        url = self.base_url
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone,
            "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,weather_code",
            "past_hours": lookback_hours
        }

        max_retries = 3
        retry_delay = 2
        timeout = 30

        logger.info(
            f"Calling Weather API: {url} | Lat={latitude}, Lon={longitude}, "
            f"Timezone={timezone}, Lookback={lookback_hours} hours"
        )

        for attempt in range(1, max_retries + 1):
            try:
                response = requests.get(url, params=params, timeout=timeout)

                # 4xx Client Error - abort retries immediately
                if 400 <= response.status_code < 500:
                    logger.error(
                        f"Client error from Weather API: "
                        f"status={response.status_code}, url={response.url}"
                    )
                    response.raise_for_status()

                # 5xx Server Error - retry
                if 500 <= response.status_code < 600:
                    logger.warning(
                        f"Attempt {attempt}/{max_retries} failed with status {response.status_code}."
                    )
                    if attempt == max_retries:
                        response.raise_for_status()
                    time.sleep(retry_delay)
                    continue

                response.raise_for_status()
                payload = response.json()

                if "hourly" not in payload:
                    raise ValueError(
                        f"Invalid response from Weather API: 'hourly' field is missing."
                    )

                logger.info("Successfully fetched weather data.")
                return payload

            except requests.exceptions.HTTPError as e:
                error_response = e.response
                status_code = error_response.status_code if error_response is not None else None

                if status_code is not None and 400 <= status_code < 500:
                    logger.error(
                        f"HTTP Client Error {status_code} from Weather API: {e} - Aborting."
                    )
                    raise

                logger.warning(
                    f"Attempt {attempt}/{max_retries} failed with HTTP status "
                    f"{status_code}: {e}"
                )
                if attempt == max_retries:
                    raise
                time.sleep(retry_delay)

            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"Attempt {attempt}/{max_retries} failed with connection error: {e}"
                )
                if attempt == max_retries:
                    raise
                time.sleep(retry_delay)

        raise RuntimeError("Failed to fetch weather data after max retries.")
