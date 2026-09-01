import os
import json
from typing import List, Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Bulletproof loading of .env from backend root relative to this file
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env_path = os.path.join(backend_dir, ".env")
load_dotenv(dotenv_path=env_path)

# Intercept and preprocess DATABASE_URL (convert postgres:// to postgresql:// for SQLAlchemy)
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    os.environ["DATABASE_URL"] = db_url.replace("postgres://", "postgresql://", 1)

# Intercept and preprocess CORS_ORIGINS (convert comma-separated string to JSON list for Pydantic)
cors_env = os.getenv("CORS_ORIGINS")
if cors_env and not cors_env.startswith("["):
    origins = [o.strip() for o in cors_env.split(",") if o.strip()]
    os.environ["CORS_ORIGINS"] = json.dumps(origins)

class Settings(BaseSettings):
    PROJECT_NAME: str = "Nexora AI API"
    API_V1_STR: str = "/api/v1"
    
    # Security — JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super_secret_key_for_nexora_ai_agency_19827361")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Login Rate Limiting
    LOGIN_MAX_ATTEMPTS: int = 5       # max failed attempts per IP per window
    LOGIN_LOCKOUT_SECONDS: int = 60   # lockout window in seconds
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'nexora.db')}"
    )
    
    # Default Admin User — MUST be set via environment variables in production
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD")

    # Outreach settings
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.example.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: Optional[str] = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    SMTP_FROM_EMAIL: Optional[str] = os.getenv("SMTP_FROM_EMAIL")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "Nexora AI")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")

    OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")

    IMAP_HOST: Optional[str] = os.getenv("IMAP_HOST", "imap.example.com")
    IMAP_PORT: int = int(os.getenv("IMAP_PORT", "993"))
    IMAP_USERNAME: Optional[str] = os.getenv("IMAP_USERNAME")
    IMAP_PASSWORD: Optional[str] = os.getenv("IMAP_PASSWORD")

    EMAIL_TEST_MODE: bool = os.getenv("EMAIL_TEST_MODE", "true").lower() in ("true", "1", "yes")
    EMAIL_TEST_RECIPIENT: Optional[str] = os.getenv("EMAIL_TEST_RECIPIENT", "your-test-email@example.com")

    # Autonomous Auto-Sender configurations
    AUTONOMOUS_SEND_INTERVAL_HOURS: int = int(os.getenv("AUTONOMOUS_SEND_INTERVAL_HOURS", "3"))
    AUTONOMOUS_BATCH_SIZE: int = int(os.getenv("AUTONOMOUS_BATCH_SIZE", "100"))
    AUTONOMOUS_DELAY_MIN: int = int(os.getenv("AUTONOMOUS_DELAY_MIN", "30"))
    AUTONOMOUS_DELAY_MAX: int = int(os.getenv("AUTONOMOUS_DELAY_MAX", "90"))

    # CORS Origins
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]

    class Config:
        case_sensitive = True

settings = Settings()
