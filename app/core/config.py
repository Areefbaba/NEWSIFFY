from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings read from the environment or a local .env file."""

    app_name: str = "Newsify"
    environment: str = "development"
    database_url: str = "sqlite:///./data/newsify.db"
    log_level: str = "INFO"
    sources_config_path: Path = Path("config/sources.yaml")

    model_config = SettingsConfigDict(env_file=".env", env_prefix="NEWSIFY_")


@lru_cache
def get_settings() -> Settings:
    return Settings()
