from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    app_password: str = "changeme"
    secret_key: str = "change-this-secret-key-in-production"
    anthropic_api_key: str = ""
    database_url: str = "sqlite+aiosqlite:///./cut_the_fat.db"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
