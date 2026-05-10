import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine the path to the root .env file
# This file is at apps/backend/app/core/config.py
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
ENV_FILE_PATH = os.path.join(ROOT_DIR, ".env")

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE_PATH, env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="local")
    log_level: str = Field(default="INFO")
    backend_host: str = Field(default="0.0.0.0")
    backend_port: int = Field(default=8000)

    database_url: str
    sync_database_url: str
    redis_url: str = Field(default="")

    chroma_host: str = Field(default="localhost")
    chroma_port: int = Field(default=8000)

    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_chat_model: str = Field(default="mistral")
    ollama_fallback_model: str = Field(default="llama3")
    ollama_embed_model: str = Field(default="nomic-embed-text")
    #openai_api_key: str | None = None
    groq_api_key: str | None = ""

    cors_origins: list[str]


@lru_cache
def get_settings() -> Settings:
    return Settings()
