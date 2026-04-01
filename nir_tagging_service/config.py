from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "tagging-subsystem"
    api_prefix: str = "/api/v1/tagging"
    database_url: str = "postgresql+psycopg://tagging:tagging@localhost:5432/tagging"
    embedding_model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    openai_base_url: str | None = Field(default=None, validation_alias="OPENAI_BASE_URL")
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_project: str | None = Field(default=None, validation_alias="OPENAI_PROJECT")
    openai_model: str | None = Field(default=None, validation_alias="OPENAI_MODEL")
    openai_timeout_seconds: int = Field(default=30, validation_alias="OPENAI_TIMEOUT_SECONDS")
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_prefix="TAGGING_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
