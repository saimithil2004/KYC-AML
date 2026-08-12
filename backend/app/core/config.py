import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import model_validator


class Settings(BaseSettings):
    PROJECT_NAME: str = "AML & KYC Compliance Platform"
    API_V1_STR: str = "/api/v1"
    VERSION: str = "15.0.0"

    # Environment
    ENV: str = "development"

    # ── Security — JWT ─────────────────────────────────────────────────────
    # REQUIRED: Must be set in .env. No hardcoded default.
    # Generate: python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY: str = "CHANGE_ME_generate_with_secrets_token_hex_32"
    # REQUIRED: Must be set in .env. No hardcoded default.
    ENCRYPTION_KEY: str = "CHANGE_ME_generate_with_secrets_token_hex_32"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    COOKIE_SECURE: bool = False

    # ── Security — Account Lockout ─────────────────────────────────────────
    MAX_LOGIN_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_MINUTES: int = 30

    # ── Security — Password Policy ─────────────────────────────────────────
    PASSWORD_MIN_LENGTH: int = 12
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_DIGITS: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = True
    PASSWORD_HISTORY_COUNT: int = 5
    PASSWORD_EXPIRY_DAYS: int = 90

    # ── MFA ────────────────────────────────────────────────────────────────
    MFA_ISSUER: str = "AML-KYC Platform"
    MFA_REQUIRED_ROLES: List[str] = ["admin", "compliance_officer"]

    # ── Rate Limiting ──────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 100
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10
    RATE_LIMIT_ENABLED: bool = True

    # ── CORS ───────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # ── Database ───────────────────────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://compliance_admin:SecretSecurePassword99@localhost:5432/aml_compliance_db"
    )
    DATABASE_REPLICA_URL: str = ""
    UPLOAD_DIR: str = "/app/shared_docs"
    MAX_UPLOAD_SIZE_MB: int = 10

    # ── Redis & Celery ─────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 300
    REDIS_SENTINELS: str = ""
    REDIS_SENTINEL_SERVICE_NAME: str = "mymaster"
    REDIS_CLUSTER_MODE: bool = False

    # ── Kubernetes & DevOps ────────────────────────────────────────────────
    KUBERNETES_NAMESPACE: str = "aml-compliance"
    DOCKER_IMAGE_VERSION: str = "16.0.0"
    GIT_COMMIT: str = "unknown"
    PROMETHEUS_METRICS_ENABLED: bool = True

    # ── Backup ─────────────────────────────────────────────────────────────
    BACKUP_DIR: str = "./backups"
    BACKUP_RETENTION_DAYS: int = 30
    BACKUP_COMPRESSION: bool = True

    # ── Logging ────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "./logs"
    LOG_JSON: bool = True

    # ── AI Providers ───────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    # ── PEP & Sanctions Provider Selection ────────────────────────────────
    # Explicit override: opensanctions | worldcheck | dowjones | mock
    PEP_PROVIDER: str = ""
    # Explicit override: opensanctions | ofac | worldcheck | dowjones | mock
    SANCTIONS_PROVIDER: str = ""

    # ── OpenSanctions ──────────────────────────────────────────────────────
    OPEN_SANCTIONS_API_KEY: str = ""
    OPEN_SANCTIONS_BASE_URL: str = "https://api.opensanctions.org"
    OPEN_SANCTIONS_TIMEOUT: int = 10
    OPEN_SANCTIONS_CACHE_TTL: int = 3600

    # ── OFAC ───────────────────────────────────────────────────────────────
    OFAC_API_KEY: str = ""
    OFAC_API_SEARCH_URL: str = "https://api.ofac-api.com/v2/search"
    OFAC_MIN_SCORE: float = 70.0
    OFAC_TIMEOUT: int = 10
    OFAC_CACHE_TTL: int = 3600

    # ── World-Check (Refinitiv) ────────────────────────────────────────────
    WORLD_CHECK_API_KEY: str = ""
    WORLD_CHECK_API_SECRET: str = ""
    WORLD_CHECK_BASE_URL: str = (
        "https://rms-world-check-one-api-pilot.thomsonreuters.com/v2"
    )
    WORLD_CHECK_GROUP_ID: str = ""
    WORLD_CHECK_TIMEOUT: int = 15
    WORLD_CHECK_CACHE_TTL: int = 3600

    # ── Dow Jones ──────────────────────────────────────────────────────────
    DOW_JONES_API_KEY: str = ""
    DOW_JONES_API_SECRET: str = ""
    DOW_JONES_BASE_URL: str = "https://api.dowjones.com/risk-and-compliance/v1"
    DOW_JONES_TOKEN_URL: str = "https://accounts.dowjones.com/oauth2/v1/token"
    DOW_JONES_TIMEOUT: int = 15
    DOW_JONES_CACHE_TTL: int = 3600

    # ── Companies House (UK) ───────────────────────────────────────────────
    COMPANIES_HOUSE_API_KEY: str = ""
    COMPANIES_HOUSE_BASE_URL: str = (
        "https://api.company-information.service.gov.uk"
    )
    COMPANIES_HOUSE_TIMEOUT: int = 10
    COMPANIES_HOUSE_CACHE_TTL: int = 1800

    @model_validator(mode="after")
    def configure_environment(self) -> "Settings":
        # Enforce HTTPS cookies in production
        if self.ENV == "production":
            self.COOKIE_SECURE = True

        # Production safety: reject placeholder secrets
        _WEAK_DEFAULTS = {
            "CHANGE_ME_generate_with_secrets_token_hex_32",
            "VerySecretJWTKeyForTokens_ReplaceInProduction",
            "StrongAESKeyForPIIEncryptionBase64String=",
            "",
        }
        if self.ENV == "production":
            if self.SECRET_KEY in _WEAK_DEFAULTS or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "SECRET_KEY must be a strong random string (32+ chars). "
                    "Generate: python -c \"import secrets; print(secrets.token_hex(32))\""
                )
            if self.ENCRYPTION_KEY in _WEAK_DEFAULTS or len(self.ENCRYPTION_KEY) < 32:
                raise ValueError(
                    "ENCRYPTION_KEY must be a strong random string (32+ chars). "
                    "Generate: python -c \"import secrets; print(secrets.token_hex(32))\""
                )

        return self

    class Config:
        case_sensitive = True
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
