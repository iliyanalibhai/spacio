from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongodb_uri: str = Field(default="mongodb://localhost:27017")
    database_name: str = Field(default="spacio")

    # NOTE: a hardcoded default secret and a wildcard CORS origin are known
    # Tier 2 security issues carried over from the v1 audit. Fixing them
    # (require jwt_secret with no default, fail fast at startup if unset,
    # require explicit CORS origins) is scheduled for Phase 1 — see
    # docs/DOCUMENTATION.md §7. Tracked here, not silently ignored.
    jwt_secret: str = Field(default="super-secret-key")
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60 * 24)
    cors_origins: List[str] = Field(default=["*"])

    # Resolved 2026-08-10: the v1 prototype disagreed with itself on this
    # number (business plan said 10-15%, financial model assumed 20%,
    # config.py had 0.20, env.example had 0.10). 20% is now the single
    # source of truth — see docs/DOCUMENTATION.md §5 and §10.
    service_fee_rate: float = Field(default=0.20)

    # $10/box/month, prorated by stay length like everything else in the
    # pricing formula. See docs/DOCUMENTATION.md §5.
    box_price_per_month: float = Field(default=10.0)

    refundable_deposit: float = Field(default=50.0)

    stripe_secret_key: str = Field(default="")
    stripe_publishable_key: str = Field(default="")
    stripe_webhook_secret: str = Field(default="")

    frontend_url: str = Field(default="http://localhost:5173")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value):
        """Accept either a JSON list or a comma-separated string.

        pydantic-settings expects JSON for list-typed env vars by default,
        but a single bare origin (CORS_ORIGINS=http://localhost:5173) reads
        naturally as a plain string. Supporting both avoids a footgun where
        the env.example format silently fails to parse.
        """
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                return value
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
