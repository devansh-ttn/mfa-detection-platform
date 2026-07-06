from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "MFA Detection Platform"
    env: str = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://mfa:mfa@localhost:5432/mfa"
    database_echo: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
