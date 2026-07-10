import os
from pydantic_settings import BaseSettings
from pydantic import model_validator

class Settings(BaseSettings):
    PROJECT_NAME: str = "AML & KYC Compliance Platform"
    API_V1_STR: str = "/api/v1"
    
    # Environment
    ENV: str = "development"
    
    # Security
    SECRET_KEY: str = "VerySecretJWTKeyForTokens_ReplaceInProduction"
    ENCRYPTION_KEY: str = "StrongAESKeyForPIIEncryptionBase64String="
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    COOKIE_SECURE: bool = False

    @model_validator(mode="after")
    def set_cookie_secure(self) -> "Settings":
        if self.ENV == "production":
            self.COOKIE_SECURE = True
        return self
    
    # DB
    DATABASE_URL: str = "postgresql+asyncpg://compliance_admin:SecretSecurePassword99@postgres:5432/aml_compliance_db"
    UPLOAD_DIR: str = "/app/shared_docs"
    MAX_UPLOAD_SIZE_MB: int = 10
    
    # Redis & Celery
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Third-Party Integrations (Placeholders)
    COMPANIES_HOUSE_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
