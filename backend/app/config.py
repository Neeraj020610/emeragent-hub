from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Emergent Central Hub"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # Database & Redis (Phase 3.2 Fail-Closed Configuration)
    DATABASE_URL: str = "sqlite:///./emergent_hub.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_KEY_PREFIX: str = "ech:otp:transient"
    REDIS_SOCKET_TIMEOUT: float = 2.0

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Integrations
    EMAIL_API_BASE_URL: str = "https://m.phx.co.in/automation/api/email-api"
    EMAIL_API_ENABLED: bool = True  # Global integration switch enabled after Phase 6.5 security verification
    EMAIL_API_INITIAL_DELAY_SECONDS: int = 5
    EMAIL_API_RETRY_INTERVAL_SECONDS: int = 5
    EMAIL_API_MAX_WAIT_SECONDS: int = 90
    EMAIL_API_MAX_ATTEMPTS: int = 12
    EMAIL_API_HTTP_TIMEOUT_SECONDS: int = 20
    EMERGENT_API_BASE_URL: str = "https://api.emergent.ai"
    EMERGENT_EXECUTION_ENABLED: bool = True  # Phase 7: Real Emergent browser automation (with 50% credit guard)

    # Initial Admin Seed
    INITIAL_ADMIN_EMAIL: str = "admin@emergent-hub.com"
    INITIAL_ADMIN_PASSWORD: str = "EmergentAdmin2026!"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
