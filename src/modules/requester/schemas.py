from datetime import datetime, timezone
from typing import List, Optional
from beanie import PydanticObjectId
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer
from ...models.ticket_model import EstadoEnum


def _serialize_utc(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


class RequesterTicketResponse(BaseModel):
    """Vista simplificada y segura del ticket para el solicitante (sin operador, prioridad ni notas internas)."""

    id: PydanticObjectId
    identificador: str
    titulo: str
    descripcion: str
    estado: EstadoEnum
    imagenes: List[str] = Field(default_factory=list)
    fecha_creacion: datetime
    fecha_edicion: Optional[datetime] = None

    @field_serializer("fecha_creacion", "fecha_edicion", when_used="json")
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        return _serialize_utc(dt)

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class RequesterTicketsSessionResponse(BaseModel):
    linked_email: Optional[str] = None
    local_tickets_count: int = 0
    items: List[RequesterTicketResponse] = Field(default_factory=list)


class RequesterRequestCodeInput(BaseModel):
    correo: EmailStr


class RequesterRequestCodeResponse(BaseModel):
    message: str
    expira_en: datetime

    @field_serializer("expira_en", when_used="json")
    def serialize_expira(self, dt: Optional[datetime]) -> Optional[str]:
        return _serialize_utc(dt)


class RequesterVerifyCodeInput(BaseModel):
    correo: EmailStr
    codigo: str = Field(..., min_length=4, max_length=12)


class OperatorGenerateCodeInput(BaseModel):
    correo: EmailStr


class AccessCodeItemResponse(BaseModel):
    id: PydanticObjectId
    correo: EmailStr
    codigo: str
    estado: str
    solicitado_por: str
    generado_por: Optional[str] = None
    creado_en: datetime
    expira_en: datetime
    usado_en: Optional[datetime] = None

    @field_serializer("creado_en", "expira_en", "usado_en", when_used="json")
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        return _serialize_utc(dt)

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )
