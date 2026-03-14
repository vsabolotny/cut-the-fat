from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

# .env lives at the project root, one level above backend/
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
# DB is always stored next to the backend package, regardless of working directory
_DB_PATH = Path(__file__).resolve().parents[1] / "cut_the_fat.db"
_DB_DEFAULT = f"sqlite+aiosqlite:///{_DB_PATH}"


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    database_url: str = _DB_DEFAULT

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
