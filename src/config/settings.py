from typing import List
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
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
