"""Production config — 12-Factor: tất cả từ environment variables."""
import os
import logging
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)


@dataclass
class Settings:
    # Server
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")

    # App
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "Production AI Agent"))
    app_version: str = field(default_factory=lambda: os.getenv("APP_VERSION", "1.0.0"))

    # LLM
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openrouter_api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    openrouter_base_url: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    )
    llm_model: str = field(
        default_factory=lambda: os.getenv(
            "OPENROUTER_MODEL",
            os.getenv("OPENAI_MODEL", os.getenv("LLM_MODEL", "gpt-4o-mini")),
        )
    )
    jina_api_key: str = field(default_factory=lambda: os.getenv("JINA_API_KEY", ""))
    cohere_api_key: str = field(default_factory=lambda: os.getenv("COHERE_API_KEY", ""))
    weaviate_url: str = field(default_factory=lambda: os.getenv("WEAVIATE_URL", ""))
    weaviate_api_key: str = field(default_factory=lambda: os.getenv("WEAVIATE_API_KEY", ""))
    pageindex_api_key: str = field(default_factory=lambda: os.getenv("PAGEINDEX_API_KEY", ""))

    # Security
    agent_api_key: str = field(default_factory=lambda: os.getenv("AGENT_API_KEY", "dev-key-change-me"))
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET", "dev-jwt-secret"))
    allowed_origins: list = field(
        default_factory=lambda: os.getenv("ALLOWED_ORIGINS", "*").split(",")
    )

    # Rate limiting
    rate_limit_per_minute: int = field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))
    )

    # Budget
    daily_budget_usd: float = field(
        default_factory=lambda: float(os.getenv("DAILY_BUDGET_USD", "5.0"))
    )

    # Storage
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", ""))

    def validate(self):
        logger = logging.getLogger(__name__)
        if self.environment == "production":
            if self.agent_api_key == "dev-key-change-me":
                raise ValueError("AGENT_API_KEY must be set in production!")
            if self.jwt_secret == "dev-jwt-secret":
                raise ValueError("JWT_SECRET must be set in production!")
        if not self.openai_api_key and not self.openrouter_api_key:
            logger.warning("No OPENAI_API_KEY or OPENROUTER_API_KEY set - RAG generation will use fallback")
        if not self.jina_api_key:
            logger.warning("No JINA_API_KEY set - reranking will use original retrieval scores")
        if not self.cohere_api_key:
            logger.warning("No COHERE_API_KEY set - semantic embeddings may fall back")
        if not self.weaviate_url or not self.weaviate_api_key:
            logger.warning("No WEAVIATE_URL/WEAVIATE_API_KEY set - vector DB retrieval may fall back")
        return self


settings = Settings().validate()
