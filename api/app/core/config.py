import json
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongodb_uri: str = Field(default="mongodb://localhost:27017")
    database_name: str = Field(default="spacio")

    # No default: an unset JWT_SECRET must fail startup rather than silently
    # signing tokens with a well-known string. See docs/DOCUMENTATION.md §7.
    jwt_secret: str
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60 * 24)

    # Whether the login cookie requires HTTPS (the `Secure` cookie
    # attribute). Must be False for local dev (uvicorn/Vite serve over
    # plain http://localhost) but MUST be set True in any real deployment —
    # otherwise the session cookie would be sent over unencrypted
    # connections too. See docs/DOCUMENTATION.md §7.
    cookie_secure: bool = Field(default=False)

    # Deliberately typed as `str`, not `List[str]`: pydantic-settings tries
    # to JSON-decode env values for List-typed fields *before* any
    # validator runs, which crashes startup on a plain value like
    # `CORS_ORIGINS=http://localhost:5173` (not valid JSON). Kept as a raw
    # string and parsed in `cors_origins_list` instead, which accepts both
    # a single origin, a comma-separated list, or a JSON array.
    #
    # No default, and "*" is rejected below: a wildcard origin combined with
    # allow_credentials=True (main.py) lets any site read authenticated
    # responses. See docs/DOCUMENTATION.md §7.
    cors_origins: str

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

    # Semantic listing matching (app/ml/embeddings.py). When False, the
    # sentence-transformers model is never loaded and /matching/recommend
    # falls back to a non-semantic ranking (ZIP + price only). The test
    # suite sets EMBEDDINGS_ENABLED=false so the ~90 MB model download and
    # ~1 s load don't happen for tests that have nothing to do with
    # matching; real deployments leave it True. See docs/DOCUMENTATION.md §3.
    embeddings_enabled: bool = Field(default=True)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("cors_origins")
    @classmethod
    def reject_wildcard_cors(cls, value: str) -> str:
        if value.strip() == "*":
            raise ValueError(
                "CORS_ORIGINS='*' is not allowed with allow_credentials=True "
                "(main.py) — list explicit origins instead, e.g. "
                "'http://localhost:5173' or a comma-separated list."
            )
        return value

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse cors_origins into a list, accepting a JSON array, a
        comma-separated string, or a single bare origin."""
        stripped = self.cors_origins.strip()
        if stripped.startswith("["):
            return json.loads(stripped)
        return [origin.strip() for origin in stripped.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    # mypy sees jwt_secret/cors_origins as required constructor args since
    # they have no default; pydantic-settings actually fills them from env
    # vars/`.env` at runtime, which mypy's static view can't see.
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
