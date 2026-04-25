from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    host: str = "0.0.0.0"
    port: int = 3000
    
    max_request_body_bytes: int = 1048576  # 1 MB
    idempotency_ttl_seconds: float = 86400.0  # 24 hours
    idempotency_sweep_interval_seconds: float = 60.0
    payment_simulated_delay_seconds: float = 2.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache()
def get_settings() -> Settings:
    return Settings()