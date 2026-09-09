"""Application settings loaded from environment variables.

Design decision: We use pydantic-settings for type-safe, validated configuration
with environment variable override support. No secrets are hardcoded.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings with environment variable overrides."""

    # --- Application ---
    app_name: str = Field(default="MemoForge", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=False, alias="APP_DEBUG")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    mock_mode: bool = Field(default=True, alias="MOCK_MODE")

    # --- Integrations ---
    integration_mode: str = Field(
        default="mock", alias="INTEGRATION_MODE",
        description="Integration mode: 'mock' uses synthetic connectors, 'real' uses live bank APIs.",
    )

    # --- Database ---
    database_url: str = Field(
        default="postgresql://memoforge:memoforge@localhost:5432/memoforge",
        alias="DATABASE_URL",
    )
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")

    # --- Redis ---
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # --- JWT ---
    jwt_secret_key: str = Field(
        default="change-me-to-a-random-secret-in-production",
        alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expiration_minutes: int = Field(default=480, alias="JWT_EXPIRATION_MINUTES")

    # --- LLM ---
    llm_provider: str = Field(default="anthropic", alias="LLM_PROVIDER")
    llm_api_key: Optional[str] = Field(default=None, alias="LLM_API_KEY")
    llm_model: str = Field(default="claude-sonnet-4-20250514", alias="LLM_MODEL")
    llm_timeout: int = Field(default=120, alias="LLM_TIMEOUT")
    llm_max_retries: int = Field(default=3, alias="LLM_MAX_RETRIES")

    # Azure
    azure_openai_endpoint: Optional[str] = Field(default=None, alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_deployment: Optional[str] = Field(default=None, alias="AZURE_OPENAI_DEPLOYMENT")

    # Bedrock
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    aws_access_key_id: Optional[str] = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")

    # Ollama
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")

    # --- Embeddings ---
    embedding_provider: str = Field(default="tfidf", alias="EMBEDDING_PROVIDER")
    embedding_api_key: Optional[str] = Field(default=None, alias="EMBEDDING_API_KEY")
    embedding_model: str = Field(default="voyage-finance-2", alias="EMBEDDING_MODEL")

    # --- RAG ---
    rag_top_k: int = Field(default=10, alias="RAG_TOP_K")
    rag_acl_enabled: bool = Field(default=True, alias="RAG_ACL_ENABLED")

    # --- Notifications ---
    smtp_host: Optional[str] = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: Optional[str] = Field(default=None, alias="SMTP_USER")
    smtp_password: Optional[str] = Field(default=None, alias="SMTP_PASSWORD")
    smtp_from: str = Field(default="noreply@memoforge.local", alias="SMTP_FROM")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def use_mock_llm(self) -> bool:
        """Use mock LLM only when MOCK_MODE=true.

        When MOCK_MODE=false and API key is missing, the LLM factory
        raises LLMProviderError instead of silently falling back to mock.
        """
        return self.mock_mode


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
