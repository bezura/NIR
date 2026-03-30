from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "tagging-subsystem"
    api_prefix: str = "/api/v1/tagging"
    database_url: str = "postgresql+psycopg://tagging:tagging@localhost:5432/tagging"
    embedding_model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    llm_api_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_timeout_seconds: int = 30
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_prefix="TAGGING_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
