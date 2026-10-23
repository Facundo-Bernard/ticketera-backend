from typing import List, Any
import json
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Tickets API"
    
    # Configuración de Base de Datos MongoDB
    MONGO_ROOT_USER: str = ""
    MONGO_ROOT_PASSWORD: str = ""
    MONGO_HOST: str = "mongodb-central"
    MONGO_PORT: int = 27017
    MONGO_DB_NAME: str = "tickets_db"
    MONGO_AUTH_SOURCE: str = "admin"
    MONGO_URI: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.MONGO_URI:
            if self.MONGO_ROOT_USER and self.MONGO_ROOT_PASSWORD:
                self.MONGO_URI = f"mongodb://{self.MONGO_ROOT_USER}:{self.MONGO_ROOT_PASSWORD}@{self.MONGO_HOST}:{self.MONGO_PORT}/{self.MONGO_DB_NAME}?authSource={self.MONGO_AUTH_SOURCE}"
            else:
                self.MONGO_URI = f"mongodb://{self.MONGO_HOST}:{self.MONGO_PORT}/{self.MONGO_DB_NAME}"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    # Límites de Seguridad y Rate Limiting
    MAX_DAILY_TICKETS_PER_EMAIL: int = 8
    TICKET_CREATION_COOLDOWN_SECONDS: int = 60
    ADMIN_EMAILS: List[str] = []

    # Configuración de Autenticación y JWT (Debe definirse en .env)
    MASTER_ADMIN_EMAIL: str = "admin@sistemas.com"
    MASTER_ADMIN_PASSWORD: str = ""
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 horas
    COOKIE_SECURE: bool = False

    # Configuración Web Push (VAPID) (Debe definirse en .env)
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_CLAIMS_EMAIL: str = ""


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
