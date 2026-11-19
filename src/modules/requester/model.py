from datetime import datetime, timezone
from typing import Literal, Optional
from beanie import Document, Indexed
from pydantic import EmailStr, Field
from pymongo import ASCENDING, DESCENDING, IndexModel


AccessCodeStatus = Literal["pendiente", "usado", "revocado", "expirado"]
AccessCodeSource = Literal["usuario", "operador"]


class RequesterAccessCode(Document):
    """Código temporal de un solo uso para vincular el historial completo de un solicitante."""

    correo: Indexed(EmailStr)
    codigo: str = Field(..., min_length=6, max_length=12)
    estado: AccessCodeStatus = Field(default="pendiente")
    solicitado_por: AccessCodeSource = Field(default="usuario")
    generado_por: Optional[str] = Field(default=None)
    creado_en: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expira_en: datetime
    usado_en: Optional[datetime] = Field(default=None)
    intentos_fallidos: int = Field(default=0, ge=0)

    class Settings:
        name = "requester_access_codes"
        indexes = [
            IndexModel([("correo", ASCENDING), ("estado", ASCENDING), ("creado_en", DESCENDING)]),
            IndexModel([("expira_en", ASCENDING)], expireAfterSeconds=86400),
        ]
