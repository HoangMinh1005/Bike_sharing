import os
from functools import lru_cache
from typing import Any, Dict, Optional


try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    HAS_PYDANTIC_SETTINGS = True
except ImportError:
    HAS_PYDANTIC_SETTINGS = False


def _clean_env_value(value: Any) -> Optional[str]:
    """
    Clean environment variable value.

    This is mainly used by the fallback Settings class when pydantic-settings
    is not installed.

    Examples:
    - '"abc"' -> 'abc'
    - "'abc'" -> 'abc'
    - " abc " -> "abc"
    """
    if value is None:
        return None

    return str(value).strip().strip('"').strip("'")


def _load_dotenv_manually(env_path: str = ".env") -> Dict[str, str]:
    """
    Manually parse a simple .env file.

    This fallback parser supports simple KEY=VALUE lines.
    It ignores empty lines and comments.
    """
    env_dict: Dict[str, str] = {}

    if not os.path.exists(env_path):
        return env_dict

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                cleaned_line = line.strip()

                if not cleaned_line or cleaned_line.startswith("#"):
                    continue

                parts = cleaned_line.split("=", 1)

                if len(parts) != 2:
                    continue

                key = parts[0].strip()
                value = _clean_env_value(parts[1].strip())

                if key and value is not None:
                    env_dict[key] = value

    except Exception:
        # Avoid breaking Airflow DAG parsing if .env cannot be read.
        pass

    return env_dict


def _get_str(env_dict: Dict[str, str], name: str, default: str) -> str:
    """
    Read string config value from os.environ first, then .env dict.
    """
    raw_value = os.getenv(name)

    if raw_value is None:
        raw_value = env_dict.get(name)

    cleaned_value = _clean_env_value(raw_value)

    if cleaned_value is None or cleaned_value == "":
        return default

    return cleaned_value


def _get_float(env_dict: Dict[str, str], name: str, default: float) -> float:
    """
    Read float config value safely.

    If the value is missing or invalid, return default.
    """
    raw_value = os.getenv(name)

    if raw_value is None:
        raw_value = env_dict.get(name)

    cleaned_value = _clean_env_value(raw_value)

    if cleaned_value is None or cleaned_value == "":
        return default

    try:
        return float(cleaned_value)
    except (TypeError, ValueError):
        return default


def _get_int(env_dict: Dict[str, str], name: str, default: int) -> int:
    """
    Read integer config value safely.

    If the value is missing or invalid, return default.
    """
    raw_value = os.getenv(name)

    if raw_value is None:
        raw_value = env_dict.get(name)

    cleaned_value = _clean_env_value(raw_value)

    if cleaned_value is None or cleaned_value == "":
        return default

    try:
        return int(cleaned_value)
    except (TypeError, ValueError):
        return default


if HAS_PYDANTIC_SETTINGS:

    class Settings(BaseSettings):
        """
        Application settings loaded from environment variables or .env file.

        This version is used when pydantic-settings is installed.
        """

        # Database configuration
        DATABASE_URL: str = (
            "postgresql+psycopg2://postgres:postgres@postgres:5432/bike_sharing"
        )

        # GBFS configuration
        GBFS_BASE_URL: str = "https://gbfs.lyft.com/gbfs/2.3/bkn/en"
        GBFS_LANGUAGE: str = "en"

        # Application environment
        ENV: str = "development"

        # Weather API configuration
        WEATHER_API_BASE_URL: str = "https://api.open-meteo.com/v1/forecast"
        WEATHER_LOCATION_NAME: str = "brooklyn"
        WEATHER_LATITUDE: float = 40.6782
        WEATHER_LONGITUDE: float = -73.9442
        WEATHER_TIMEZONE: str = "America/New_York"
        WEATHER_LOOKBACK_HOURS: int = 24

        # Calendar configuration
        CALENDAR_CSV_PATH: str = "/opt/airflow/data/calendar.csv"
        CALENDAR_COUNTRY_CODE: str = "US"
        CALENDAR_START_DATE: str = "2026-01-01"
        CALENDAR_END_DATE: str = "2026-12-31"

        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
        )

        def get_gbfs_feed_url(self, feed_name: str) -> str:
            """
            Build GBFS feed URL.

            Example:
            feed_name='station_status'
            -> https://.../station_status.json
            """
            return f"{self.GBFS_BASE_URL.rstrip('/')}/{feed_name}.json"

        def get_weather_api_url(self) -> str:
            """
            Return normalized Weather API base URL.
            """
            return self.WEATHER_API_BASE_URL.rstrip("/")

else:

    class Settings:
        """
        Fallback settings class for environments where pydantic-settings
        is not installed.

        This helps avoid dependency conflicts in Airflow scheduler/worker.
        """

        def __init__(self):
            env_dict = _load_dotenv_manually(".env")

            # Database configuration
            self.DATABASE_URL = _get_str(
                env_dict,
                "DATABASE_URL",
                "postgresql+psycopg2://postgres:postgres@postgres:5432/bike_sharing",
            )

            # GBFS configuration
            self.GBFS_BASE_URL = _get_str(
                env_dict,
                "GBFS_BASE_URL",
                "https://gbfs.lyft.com/gbfs/2.3/bkn/en",
            )

            self.GBFS_LANGUAGE = _get_str(
                env_dict,
                "GBFS_LANGUAGE",
                "en",
            )

            # Application environment
            self.ENV = _get_str(
                env_dict,
                "ENV",
                "development",
            )

            # Weather API configuration
            self.WEATHER_API_BASE_URL = _get_str(
                env_dict,
                "WEATHER_API_BASE_URL",
                "https://api.open-meteo.com/v1/forecast",
            )

            self.WEATHER_LOCATION_NAME = _get_str(
                env_dict,
                "WEATHER_LOCATION_NAME",
                "brooklyn",
            )

            self.WEATHER_LATITUDE = _get_float(
                env_dict,
                "WEATHER_LATITUDE",
                40.6782,
            )

            self.WEATHER_LONGITUDE = _get_float(
                env_dict,
                "WEATHER_LONGITUDE",
                -73.9442,
            )

            self.WEATHER_TIMEZONE = _get_str(
                env_dict,
                "WEATHER_TIMEZONE",
                "America/New_York",
            )

            self.WEATHER_LOOKBACK_HOURS = _get_int(
                env_dict,
                "WEATHER_LOOKBACK_HOURS",
                24,
            )

            # Calendar configuration
            self.CALENDAR_CSV_PATH = _get_str(
                env_dict,
                "CALENDAR_CSV_PATH",
                "/opt/airflow/data/calendar.csv",
            )

            self.CALENDAR_COUNTRY_CODE = _get_str(
                env_dict,
                "CALENDAR_COUNTRY_CODE",
                "US",
            )

            self.CALENDAR_START_DATE = _get_str(
                env_dict,
                "CALENDAR_START_DATE",
                "2026-01-01",
            )

            self.CALENDAR_END_DATE = _get_str(
                env_dict,
                "CALENDAR_END_DATE",
                "2026-12-31",
            )

        def get_gbfs_feed_url(self, feed_name: str) -> str:
            """
            Build GBFS feed URL.

            Example:
            feed_name='station_status'
            -> https://.../station_status.json
            """
            return f"{self.GBFS_BASE_URL.rstrip('/')}/{feed_name}.json"

        def get_weather_api_url(self) -> str:
            """
            Return normalized Weather API base URL.
            """
            return self.WEATHER_API_BASE_URL.rstrip("/")


@lru_cache()
def get_settings() -> Settings:
    """
    Return a cached settings instance.

    Note:
    If .env is changed while the container/process is running,
    restart the service or clear this cache to load new values.
    """
    return Settings()