from decimal import Decimal
from functools import lru_cache
from typing import TYPE_CHECKING

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from pydantic import FieldValidationInfo


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    environment: str = "development"
    debug: bool = False
    rule_engine_version: str = "0.1.0"

    # Database
    database_url: str  # postgresql+asyncpg://...

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str  # FIX ISSUE-02: for server-side storage ops
    supabase_jwt_secret: str

    # AI
    anthropic_api_key: str
    # FIX ISSUE-07: use str, convert to Decimal in code to avoid float precision
    ai_max_cost_per_shop_per_month_usd: str = "0.50"
    ai_max_calls_per_import: int = 3
    ai_narrative_cache_ttl_seconds: int = 3600
    ai_top_n_leaks: int = 3
    ai_top_n_skus: int = 20
    ai_top_n_refund_reasons: int = 200
    # F-1B-06: explicit per-tier AI call limits (replaces magic * 5 multiplier)
    ai_max_calls_per_import_free: int = 3
    ai_max_calls_per_import_pro: int = 10
    ai_max_calls_per_import_business: int = 15

    # Redis
    redis_url: str = "redis://localhost:6379"

    # CORS
    allowed_origins: list[str] = ["http://localhost:3000"]

    # Email (SendGrid — optional, digest disabled if not set)
    sendgrid_api_key: str = ""
    email_from_address: str = "digest@tikai.vn"
    email_from_name: str = "Tikai"
    # v2.0.1: app_base_url used for email CTA links — never hardcode tikai.vn in code
    # Default is production URL; override with staging URL in staging env
    app_base_url: str = "https://app.tikai.vn"

    @property
    def email_enabled(self) -> bool:
        return bool(self.sendgrid_api_key)

    # Sentry
    sentry_dsn: str = ""

    @field_validator("sentry_dsn", mode="after")
    @classmethod
    def require_sentry_in_production(cls, v: str, info: "FieldValidationInfo") -> str:
        """LOW-4: Fail fast if Sentry DSN missing in production.
        Without this, errors are swallowed silently when SENTRY_DSN is forgotten."""
        env = info.data.get("environment", "development")
        if env == "production" and not v:
            raise ValueError(
                "SENTRY_DSN is required when ENVIRONMENT=production. "
                "Set SENTRY_DSN env var or set ENVIRONMENT=development for local dev."
            )
        return v

    @field_validator("allowed_origins", mode="after")
    @classmethod
    def require_production_origins(cls, v: list[str], info: "FieldValidationInfo") -> list[str]:
        """F-02: Fail fast if allowed_origins still points to localhost in production.
        Prevents the common mistake of forgetting to set ALLOWED_ORIGINS in Railway env."""
        env = info.data.get("environment", "development")
        if env == "production" and any("localhost" in o for o in v):
            raise ValueError(
                "ALLOWED_ORIGINS still contains localhost in production. "
                'Set ALLOWED_ORIGINS=["https://app.tikai.vn"] in Railway environment variables.'
            )
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def ai_budget_limit(self) -> Decimal:
        return Decimal(self.ai_max_cost_per_shop_per_month_usd)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
