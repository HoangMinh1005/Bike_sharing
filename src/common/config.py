import os
from functools import lru_cache

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    HAS_PYDANTIC_SETTINGS = True
except ImportError:
    HAS_PYDANTIC_SETTINGS = False

if HAS_PYDANTIC_SETTINGS:
    class Settings(BaseSettings):
        DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@postgres:5432/bike_sharing"
        GBFS_BASE_URL: str = "https://gbfs.lyft.com/gbfs/2.3/bkn/en"
        GBFS_LANGUAGE: str = "en"
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
            extra="ignore"
        )

        def get_gbfs_feed_url(self, feed_name: str) -> str:
            return f"{self.GBFS_BASE_URL.rstrip('/')}/{feed_name}.json"
else:
    class Settings:
        """
        Fallback settings class for environments where pydantic-settings is not installed
        (such as Airflow schedulers/workers) to prevent dependency constraint conflicts.
        """
        def __init__(self):
            # Parse .env file manually if available locally
            env_dict = {}
            if os.path.exists(".env"):
                try:
                    with open(".env", "r", encoding="utf-8") as f:
                        for line in f:
                            cleaned = line.strip()
                            if cleaned and not cleaned.startswith("#"):
                                parts = cleaned.split("=", 1)
                                if len(parts) == 2:
                                    env_dict[parts[0].strip()] = parts[1].strip()
                except Exception:
                    pass

            self.DATABASE_URL = os.getenv("DATABASE_URL") or env_dict.get(
                "DATABASE_URL",
                "postgresql+psycopg2://postgres:postgres@postgres:5432/bike_sharing"
            )
            self.GBFS_BASE_URL = os.getenv("GBFS_BASE_URL") or env_dict.get(
                "GBFS_BASE_URL",
                "https://gbfs.lyft.com/gbfs/2.3/bkn/en"
            )
            self.GBFS_LANGUAGE = os.getenv("GBFS_LANGUAGE") or env_dict.get(
                "GBFS_LANGUAGE",
                "en"
            )
            self.ENV = os.getenv("ENV") or env_dict.get("ENV", "development")

            self.WEATHER_API_BASE_URL = os.getenv("WEATHER_API_BASE_URL") or env_dict.get(
                "WEATHER_API_BASE_URL", "https://api.open-meteo.com/v1/forecast"
            )
            self.WEATHER_LOCATION_NAME = os.getenv("WEATHER_LOCATION_NAME") or env_dict.get(
                "WEATHER_LOCATION_NAME", "brooklyn"
            )
            self.WEATHER_LATITUDE = float(os.getenv("WEATHER_LATITUDE") or env_dict.get(
                "WEATHER_LATITUDE", 40.6782
            ))
            self.WEATHER_LONGITUDE = float(os.getenv("WEATHER_LONGITUDE") or env_dict.get(
                "WEATHER_LONGITUDE", -73.9442
            ))
            self.WEATHER_TIMEZONE = os.getenv("WEATHER_TIMEZONE") or env_dict.get(
                "WEATHER_TIMEZONE", "America/New_York"
            )
            self.WEATHER_LOOKBACK_HOURS = int(os.getenv("WEATHER_LOOKBACK_HOURS") or env_dict.get(
                "WEATHER_LOOKBACK_HOURS", 24
            ))
            self.CALENDAR_CSV_PATH = os.getenv("CALENDAR_CSV_PATH") or env_dict.get(
                "CALENDAR_CSV_PATH", "/opt/airflow/data/calendar.csv"
            )
            self.CALENDAR_COUNTRY_CODE = os.getenv("CALENDAR_COUNTRY_CODE") or env_dict.get(
                "CALENDAR_COUNTRY_CODE", "US"
            )
            self.CALENDAR_START_DATE = os.getenv("CALENDAR_START_DATE") or env_dict.get(
                "CALENDAR_START_DATE", "2026-01-01"
            )
            self.CALENDAR_END_DATE = os.getenv("CALENDAR_END_DATE") or env_dict.get(
                "CALENDAR_END_DATE", "2026-12-31"
            )

        def get_gbfs_feed_url(self, feed_name: str) -> str:
            return f"{self.GBFS_BASE_URL.rstrip('/')}/{feed_name}.json"

@lru_cache()
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()