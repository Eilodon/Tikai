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
    rule_engine_version: str = "2.3.0"

    # Database
    database_url: str  # postgresql+asyncpg://...

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str  # FIX ISSUE-02: for server-side storage ops
    supabase_jwt_secret: str

    # AI
    anthropic_api_key: str
    # Per-tier monthly dollar budget caps (str → Decimal to avoid float precision).
    # Business users get 15 calls/import vs Free's 3 — budget must scale accordingly.
    # With Haiku ~$0.015/import: Free≈10 imports/month, Pro≈33, Business≈67.
    ai_max_cost_per_month_usd_free: str = "0.15"
    ai_max_cost_per_month_usd_pro: str = "0.50"
    ai_max_cost_per_month_usd_business: str = "1.00"
    # Legacy flat setting kept for backward compat — use ai_budget_for_tier() instead
    ai_max_cost_per_shop_per_month_usd: str = "0.50"
    ai_max_calls_per_import: int = 3
    ai_narrative_cache_ttl_seconds: int = 3600
    ai_top_n_leaks: int = 3
    ai_top_n_skus: int = 20
    ai_top_n_refund_reasons: int = 200
    # F-1B-06: explicit per-tier AI call limits (replaces magic * 5 multiplier)
    # BUG-L2 FIX: gates.py advertises Free=5 but config was 3. Aligned to 5.
    # BUG-M1 FIX: enterprise tier added (gates.py Feature.AI_CALLS_PER_IMPORT: 20).
    ai_max_calls_per_import_free: int = 5
    ai_max_calls_per_import_pro: int = 10
    ai_max_calls_per_import_business: int = 15
    ai_max_calls_per_import_enterprise: int = 20

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Database connection pool — tune per Railway plan and replica count.
    # Default: pool_size=5, max_overflow=10 → max 15 connections per API process.
    # With 2 API replicas + 1 worker: 2×15 + 10 = 40 total (safe for Supabase Pro=100).
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # CORS
    allowed_origins: list[str] = ["http://localhost:3000"]

    # Email (SendGrid — optional, digest disabled if not set)
    sendgrid_api_key: str = ""
    email_from_address: str = "digest@tikai.vn"  # override via EMAIL_FROM_ADDRESS env var
    email_from_name: str = "Tikai"
    # v2.0.1: app_base_url used for email CTA links — never hardcode tikai.vn in code
    # Default is production URL; override with staging URL in staging env
    app_base_url: str = "https://app.tikai.vn"

    @property
    def email_enabled(self) -> bool:
        return bool(self.sendgrid_api_key)

    # Web Push (VAPID)
    vapid_private_key: str = ""
    vapid_public_key: str = ""
    vapid_claims_email: str = "admin@tikai.vn"

    # Zalo ZNS (optional — sender no-ops if not set)
    zalo_oa_id: str = ""
    zalo_zns_access_token: str = ""

    @property
    def zns_enabled(self) -> bool:
        return bool(self.zalo_oa_id and self.zalo_zns_access_token)

    # Admin
    admin_secret: str = ""

    # Sentry
    sentry_dsn: str = ""

    @field_validator("supabase_jwt_secret", mode="after")
    @classmethod
    def require_supabase_jwt_secret(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(
                "SUPABASE_JWT_SECRET must not be empty. "
                "Set the value from your Supabase project settings."
            )
        return v

    @field_validator("supabase_service_role_key", mode="after")
    @classmethod
    def require_supabase_service_role_key(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(
                "SUPABASE_SERVICE_ROLE_KEY must not be empty. "
                "Set the value from your Supabase project settings."
            )
        return v

    @field_validator("anthropic_api_key", mode="after")
    @classmethod
    def require_anthropic_api_key(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(
                "ANTHROPIC_API_KEY must not be empty. Set the value from your Anthropic console."
            )
        return v

    @field_validator("admin_secret", mode="after")
    @classmethod
    def validate_admin_secret(cls, v: str) -> str:
        # Allow empty string — admin endpoints are optional.
        # If a value is provided, it must be at least 16 chars to be meaningful.
        if v and len(v) < 16:
            raise ValueError(
                "ADMIN_SECRET must be at least 16 characters long (or left empty to disable admin endpoints)."
            )
        return v

    @field_validator("sentry_dsn", mode="after")
    @classmethod
    def require_sentry_in_production(cls, v: str, info: "FieldValidationInfo") -> str:
        """LOW-4: Fail fast if Sentry DSN missing in production or staging.
        Without this, errors are swallowed silently when SENTRY_DSN is forgotten.
        F-C1-01: Extended to staging to enforce observability before production."""
        env = info.data.get("environment", "development")
        if env in ("production", "staging") and not v:
            raise ValueError(
                f"SENTRY_DSN is required when ENVIRONMENT={env}. "
                "Set SENTRY_DSN env var or set ENVIRONMENT=development for local dev."
            )
        return v

    @field_validator("database_url", mode="after")
    @classmethod
    def require_ssl_in_production(cls, v: str, info: "FieldValidationInfo") -> str:
        """Fail fast if database_url lacks SSL in production or staging.
        Unencrypted PostgreSQL over the network is unacceptable for production data.
        F-C1-01: Extended to staging to enforce security before production."""
        env = info.data.get("environment", "development")
        if env in ("production", "staging") and "sslmode" not in v and "ssl=true" not in v:
            raise ValueError(
                f"DATABASE_URL must include SSL for {env} (e.g. ?sslmode=require). "
                "Add sslmode=require to your Railway DATABASE_URL."
            )
        return v

    @field_validator("allowed_origins", mode="after")
    @classmethod
    def require_production_origins(cls, v: list[str], info: "FieldValidationInfo") -> list[str]:
        """F-02: Fail fast if allowed_origins still points to localhost in production or staging.
        Prevents the common mistake of forgetting to set ALLOWED_ORIGINS in Railway env."""
        env = info.data.get("environment", "development")
        if env in ("production", "staging") and any("localhost" in o for o in v):
            raise ValueError(
                f"ALLOWED_ORIGINS still contains localhost in {env}. "
                'Set ALLOWED_ORIGINS=["https://app.tikai.vn"] in Railway environment variables.'
            )
        return v

    @field_validator("app_base_url", mode="after")
    @classmethod
    def warn_staging_app_base_url(cls, v: str, info: "FieldValidationInfo") -> str:
        """Fail fast if staging still uses the production app_base_url default.
        Without this, email digest links from staging point to production,
        causing confusion for sellers who receive staging test emails."""
        env = info.data.get("environment", "development")
        if env == "staging" and "app.tikai.vn" in v:
            raise ValueError(
                "APP_BASE_URL still points to production (app.tikai.vn) in staging environment. "
                "Set APP_BASE_URL=https://staging.tikai.vn (or your staging URL) to prevent "
                "staging emails from linking to production."
            )
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def ai_budget_limit(self) -> Decimal:
        """Legacy flat limit — kept for backward compat. Prefer ai_budget_for_tier()."""
        return Decimal(self.ai_max_cost_per_shop_per_month_usd)

    # Per-tier monthly dollar budget for AI (enterprise same as business — no higher limit yet)
    ai_max_cost_per_month_usd_enterprise: str = "1.00"

    def ai_budget_for_tier(self, tier: str) -> Decimal:
        """Return the monthly AI dollar budget for a given subscription tier."""
        mapping = {
            "free": self.ai_max_cost_per_month_usd_free,
            "pro": self.ai_max_cost_per_month_usd_pro,
            "pro_trial": self.ai_max_cost_per_month_usd_pro,  # trial gets pro budget
            "business": self.ai_max_cost_per_month_usd_business,
            "enterprise": self.ai_max_cost_per_month_usd_enterprise,
        }
        return Decimal(mapping.get(tier, self.ai_max_cost_per_month_usd_free))


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
