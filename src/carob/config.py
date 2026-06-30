"""Runtime settings, read from the environment (and `.env` in development)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CAROB_", extra="ignore")

    env: str = "dev"
    database_url: str = "postgresql+psycopg://carob:carob@localhost:5432/carob"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_statement_timeout_ms: int = 15_000

    log_level: str = "INFO"
    log_format: str = "json"

    jwt_secret: str = Field(default="dev-only-change-me-dev-only-change-me")
    jwt_ttl_minutes: int = 8 * 60

    paystub_url: str = "http://localhost:8090"
    paystub_api_key: str = "sk_test_carob_dev"
    paystub_webhook_secret: str = "whsec_dev_carob"  # noqa: S105 (dev default; set in every real environment)
    paystub_timeout_seconds: float = 3.0

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    mail_from: str = "Carob <no-reply@carob.example>"
    mailer: str = "smtp"

    router_model_path: str | None = None
    router_confidence_threshold: float = 0.55

    public_base_url: str = "http://localhost:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
