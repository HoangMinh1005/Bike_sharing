import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Database connection string
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/bike_sharing"
    
    # GBFS feed configurations
    GBFS_BASE_URL: str = "https://gbfs.lyft.com/gbfs/2.3/bkn/en"
    GBFS_LANGUAGE: str = "en"
    
    # Environment mode (development/production/testing)
    ENV: str = "development"

    # Automatically load values from a .env file if it is present
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

@lru_cache()
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()
