import os
from typing import List
from pydantic_settings import BaseSettings
from pydantic import model_validator


class Settings(BaseSettings):
    PROJECT_NAME: str = "AML & KYC Compliance Platform"
    API_V1_STR: str = "/api/v1"
    VERSION: str = "15.0.0"

    # Environment
    ENV: str = "development"

    # Security — JWT
    SECRET_KEY: str = "VerySecretJWTKeyForTokens_ReplaceInProduction"
    ENCRYPTION_KEY: str = "StrongAESKeyForPIIEncryptionBase64String="
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    COOKIE_SECURE: bool = False

    # Security — Account Lockout
    MAX_LOGIN_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_MINUTES: int = 30

    # Security — Password Policy
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_DIGITS: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = True
    PASSWORD_HISTORY_COUNT: int = 5
    PASSWORD_EXPIRY_DAYS: int = 90

    # MFA
    MFA_ISSUER: str = "AML-KYC Platform"
    MFA_REQUIRED_ROLES: List[str] = ["admin", "compliance_officer"]

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10
    RATE_LIMIT_ENABLED: bool = True

    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # DB
    DATABASE_URL: str = (
        "postgresql+asyncpg://compliance_admin:SecretSecurePassword99@postgres:5432/aml_compliance_db"
    )
    DATABASE_REPLICA_URL: str = ""
    UPLOAD_DIR: str = "/app/shared_docs"
    MAX_UPLOAD_SIZE_MB: int = 10

    # Redis & Celery
    REDIS_URL: str = "redis://redis:6379/0"
    REDIS_CACHE_TTL: int = 300  # 5 minutes default cache TTL
    REDIS_SENTINELS: str = (
        ""  # Comma separated list of sentinel addresses like 'host1:26379,host2:26379'
    )
    REDIS_SENTINEL_SERVICE_NAME: str = "mymaster"
    REDIS_CLUSTER_MODE: bool = False

    # Kubernetes & DevOps Image Version
    KUBERNETES_NAMESPACE: str = "aml-compliance"
    DOCKER_IMAGE_VERSION: str = "16.0.0"
    GIT_COMMIT: str = "a1b2c3d4"
    PROMETHEUS_METRICS_ENABLED: bool = True

    # Backup
    BACKUP_DIR: str = "./backups"
    BACKUP_RETENTION_DAYS: int = 30
    BACKUP_COMPRESSION: bool = True

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "./logs"
    LOG_JSON: bool = True

    # Third-Party Integrations (Placeholders)
    COMPANIES_HOUSE_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    @model_validator(mode="after")
    def configure_environment(self) -> "Settings":
        if self.ENV == "production":
            self.COOKIE_SECURE = True
        return self

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()
