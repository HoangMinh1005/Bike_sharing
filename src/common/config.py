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

        def get_gbfs_feed_url(self, feed_name: str) -> str:
            return f"{self.GBFS_BASE_URL.rstrip('/')}/{feed_name}.json"

@lru_cache()
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()