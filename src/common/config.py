from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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


@lru_cache()
def get_settings() -> Settings:
    return Settings()