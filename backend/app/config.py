"""Application configuration, YAML blueprint loaders, and zero-paid policy settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"


def _load_yaml(filename: str) -> dict[str, Any]:
    path = CONFIG_DIR / filename
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str = f"sqlite:///{(DATA_DIR / 'advisory_council.db').as_posix()}"
    checkpoint_db_path: str = (DATA_DIR / "checkpoints.db").as_posix()

    # Strict Zero-Paid-Use Policy (never silently call paid endpoints)
    cost_policy_mode: str = "zero_paid"
    allow_paid_providers: bool = False
    allow_credit_card_fallback: bool = False
    allow_over_quota_requests: bool = False

    # Local Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_default_model: str = "llama3.2:3b"

    # Free Hosted Provider Keys (Server-side only)
    groq_api_key: str = ""
    google_api_key: str = ""
    hf_token: str = ""
    nvidia_api_key: str = ""
    openrouter_api_key: str = ""
    modelscope_api_key: str = ""
    mistral_api_key: str = ""
    cerebras_api_key: str = ""
    sambanova_api_key: str = ""
    cohere_api_key: str = ""
    cloudflare_api_token: str = ""
    cloudflare_account_id: str = ""

    # Research Connectors (Optional keys increase limits)
    openalex_api_key: str = ""
    openalex_email: str = ""
    github_token: str = ""
    tavily_api_key: str = ""

    # Safety & Limits
    max_upload_bytes: int = 15 * 1024 * 1024
    max_crawl_bytes: int = 2 * 1024 * 1024
    request_timeout_seconds: float = 20.0
    llm_timeout_seconds: float = 90.0
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Paths
    catalog_dir: Path = Field(default_factory=lambda: DATA_DIR / "catalog")
    documents_dir: Path = Field(default_factory=lambda: DATA_DIR / "documents")
    exports_dir: Path = Field(default_factory=lambda: DATA_DIR / "exports")
    cache_dir: Path = Field(default_factory=lambda: DATA_DIR / "cache")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    for folder in (
        DATA_DIR,
        settings.catalog_dir,
        settings.documents_dir,
        settings.exports_dir,
        settings.cache_dir,
    ):
        folder.mkdir(parents=True, exist_ok=True)
    return settings


@lru_cache
def get_agents_config() -> dict[str, Any]:
    return _load_yaml("agents.yaml")


@lru_cache
def get_providers_config() -> dict[str, Any]:
    return _load_yaml("providers.yaml")


@lru_cache
def get_models_config() -> dict[str, Any]:
    return _load_yaml("models.yaml")


@lru_cache
def get_research_sources_config() -> dict[str, Any]:
    return _load_yaml("research_sources.yaml")


@lru_cache
def get_scoring_rubrics_config() -> dict[str, Any]:
    return _load_yaml("scoring_rubrics.yaml")
