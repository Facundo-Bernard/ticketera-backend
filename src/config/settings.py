from typing import List, Any
import json
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Tickets API"
    MONGO_URI: str = "mongodb://localhost:27017/tickets_db"
    MONGO_DB_NAME: str = "tickets_db"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    # Límites de Seguridad y Rate Limiting
    MAX_DAILY_TICKETS_PER_EMAIL: int = 8
    TICKET_CREATION_COOLDOWN_SECONDS: int = 60
    ADMIN_EMAILS: List[str] = []

    # Configuración de Autenticación y JWT
    MASTER_ADMIN_EMAIL: str = "admin@sistemas.com"
    MASTER_ADMIN_PASSWORD: str = "admin123"
    JWT_SECRET_KEY: str = "coopya_sistemas_secret_jwt_key_development_2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 horas

    # Configuracion Web Push (VAPID)
    VAPID_PUBLIC_KEY: str = "BMsXWvjJkRm0nEiE1tXTx9tfaq79Wc7x3_uN4n9xMigcgi_NN1-dI58YwYK5kY8d1xtmGdbQ2oaNg9rOaaRDHbo"
    VAPID_PRIVATE_KEY: str = "mQ-RRqbL4rhbOm9YOom3MTOU3IWmFY-0DwjFgF5qCeU"
    VAPID_CLAIMS_EMAIL: str = "admin@coopya.com"


    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            v_trimmed = v.strip()
            if v_trimmed.startswith("[") and v_trimmed.endswith("]"):
                try:
                    return json.loads(v_trimmed)
                except Exception:
                    pass
            return [origin.strip() for origin in v_trimmed.split(",") if origin.strip()]
        return v or ["*"]

    @field_validator("ADMIN_EMAILS", mode="before")
    @classmethod
    def parse_admin_emails(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            v_trimmed = v.strip()
            if v_trimmed.startswith("[") and v_trimmed.endswith("]"):
                try:
                    return json.loads(v_trimmed)
                except Exception:
                    pass
            return [email.strip() for email in v_trimmed.split(",") if email.strip()]
        return v or []

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
