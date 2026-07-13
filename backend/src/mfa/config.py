from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "MFA Detection Platform"
    env: str = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://mfa:mfa@localhost:5432/mfa"
    database_echo: bool = False
    cognito_user_pool_id: str = ""
    cognito_app_client_id: str = ""
    cognito_region: str = "us-east-1"
    mfa_require_auth: bool = False
    mfa_shadow_mode: bool = False
    opensearch_endpoint: str = ""
    opensearch_index: str = "mfa-rag-v1"

    @property
    def auth_strict(self) -> bool:
        if self.env.lower() == "prod":
            return True
        return self.mfa_require_auth


@lru_cache
def get_settings() -> Settings:
    return Settings()
