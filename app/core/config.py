from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    database_url: str = Field(
        default="mysql+aiomysql://fromnear:fromnear@localhost:3306/fromnear_growth"
    )
    sync_database_url: str = Field(
        default="mysql+pymysql://fromnear:fromnear@localhost:3306/fromnear_growth"
    )
    redis_url: str = "redis://localhost:6379/0"

    chroma_host: str = "localhost"
    chroma_port: int = 8000

    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "mistral"
    ollama_fallback_model: str = "llama3"
    ollama_embed_model: str = "nomic-embed-text"
    openai_api_key: str | None = None

    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
