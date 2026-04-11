from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_base_url: str
    openai_api_key: str
    minimax_model: str
    minimax_timeout_seconds: float = 30.0
    minimax_max_retries: int = 2
    delilegal_timeout_seconds: float = 20.0
    app_log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
