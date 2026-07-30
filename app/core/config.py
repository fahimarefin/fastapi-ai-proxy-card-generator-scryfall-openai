"""
Centralized application configuration.

All values are loaded from environment variables (or a local .env file when
running outside Docker). Nothing sensitive is hard-coded here.
"""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ---- App ----
    APP_NAME: str = "AI MTG Proxy Card Generator"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # ---- Scryfall ----
    SCRYFALL_API_BASE: str = "https://api.scryfall.com"
    SCRYFALL_USER_AGENT: str = "AIMTGProxyGenerator/1.0"
    REQUEST_TIMEOUT_SECONDS: int = 60

    # ---- AI provider ----
    AI_PROVIDER: Literal["openai", "stability"] = "openai"

    OPENAI_API_KEY: str = ""
    OPENAI_IMAGE_MODEL: str = "gpt-image-1"
    OPENAI_IMAGE_SIZE: str = "1024x1024"

    STABILITY_API_KEY: str = ""
    STABILITY_MODEL: str = "stable-diffusion-xl-1024-v1-0"

    # ---- Generation ----
    DEFAULT_GENERATION_MODE: Literal["hybrid", "full_ai"] = "hybrid"
    OUTPUT_DIR: str = "outputs"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance so we don't re-parse env vars on every call."""
    return Settings()
