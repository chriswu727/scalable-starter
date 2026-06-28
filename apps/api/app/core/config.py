"""Typed application configuration (12-factor).

Nothing in the codebase reads ``os.environ`` directly — everything goes through
the single :data:`settings` object so configuration is validated once, at boot,
and is fully type-checked everywhere it is used.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, PostgresDsn, RedisDsn, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Environment = Literal["development", "staging", "production"]


class Settings(BaseSettings):
    """All runtime configuration, sourced from the environment.

    Required values without defaults will cause a fast, explicit failure at
    startup if they are missing — which is exactly what you want.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Identity / environment ----
    environment: Environment = "development"
    service_name: str = Field(default="api", alias="OTEL_SERVICE_NAME")
    version: str = "0.1.0"

    # ---- HTTP server ----
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    # NoDecode disables pydantic-settings' implicit JSON-decode of the raw env
    # value, which would otherwise raise SettingsError on a plain comma-separated
    # string (e.g. CORS_ORIGINS=http://localhost:3000) before any validator runs.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # ---- Security ----
    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    access_token_expire_minutes: int = 30
    jwt_algorithm: str = "HS256"
    # Optional JWT audience/issuer validation — set both ends to enable.
    jwt_audience: str | None = None
    jwt_issuer: str | None = None

    # ---- Logging ----
    log_level: str = "info"
    log_format: Literal["console", "json"] = "console"

    # ---- Database ----
    database_url: PostgresDsn = Field(  # type: ignore[assignment]
        default="postgresql+asyncpg://app:app@localhost:5432/app",
    )
    # Optional separate DSN for read replicas; falls back to the primary.
    database_read_url: PostgresDsn | None = None
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False

    # ---- Cache / broker ----
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")  # type: ignore[assignment]

    # ---- Observability ----
    otel_exporter_otlp_endpoint: str | None = None
    prometheus_enabled: bool = True

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tracing_enabled(self) -> bool:
        return bool(self.otel_exporter_otlp_endpoint)

    @property
    def sqlalchemy_dsn(self) -> str:
        return str(self.database_url)

    @property
    def sqlalchemy_read_dsn(self) -> str:
        return str(self.database_read_url or self.database_url)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        # Accept a comma-separated string from the environment as well as a list.
        if isinstance(value, str):
            return [o.strip() for o in value.split(",") if o.strip()]
        return value

    @model_validator(mode="after")
    def _enforce_production_safety(self) -> Settings:
        """Fail fast at boot on insecure production configuration.

        A starter that silently ships a default signing key or wildcard CORS in
        production is a footgun; refuse to start instead.
        """
        if self.environment != "production":
            return self
        if self.secret_key.startswith("change-me") or len(self.secret_key) < 32:
            raise ValueError(
                "SECRET_KEY must be a strong, non-default value in production "
                "(generate one with `openssl rand -hex 32`)."
            )
        if not self.cors_origins or "*" in self.cors_origins:
            raise ValueError(
                "CORS_ORIGINS must be an explicit allow-list in production "
                "(wildcard '*' is not permitted with credentials)."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so the environment is parsed exactly once per process."""
    return Settings()


settings = get_settings()
