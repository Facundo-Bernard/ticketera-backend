from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_serializer
from typing import Optional, List, Union
from datetime import datetime, timezone
from beanie import PydanticObjectId
from ..models.ticket_model import PrioridadEnum, EstadoEnum, Frecuencia


class TicketCreate(BaseModel):
    titulo: str = Field(..., min_length=3, max_length=150, description="Titulo conciso del ticket")
    descripcion: str = Field(..., description="Descripcion detallada del problema")
    correo: EmailStr = Field(..., description="Correo de contacto del solicitante")
    prioridad: Optional[PrioridadEnum] = Field(default=PrioridadEnum.MEDIA, description="Prioridad del ticket")
    asignar: Optional[str] = Field(default=None, description="Usuario o tecnico asignado")
    imagenes: Optional[List[str]] = Field(default_factory=list, description="Lista opcional de IDs o URLs de imagenes")
    columna: Optional[int] = Field(default=1, ge=1, le=4, description="ID numerico de la columna")
    frecuencia: Optional[Frecuencia] = Field(default=None, description="Frecuencia periodica si aplica")


class TicketUpdate(BaseModel):
    titulo: Optional[str] = Field(None, min_length=3, max_length=150)
    descripcion: Optional[str] = None
    correo: Optional[EmailStr] = None
    prioridad: Optional[PrioridadEnum] = None
    estado: Optional[EstadoEnum] = None
    asignar: Optional[str] = None
    imagenes: Optional[List[str]] = None
    columna: Optional[int] = Field(None, ge=1, le=4, description="ID numerico de la columna")
    leido: Optional[bool] = Field(None, description="Marcar como leido o no leido")
    frecuencia: Optional[Frecuencia] = Field(None, description="Actualizar frecuencia periodica")


class TicketFilter(BaseModel):
    fecha_desde: Optional[Union[datetime, str]] = None
    fecha_hasta: Optional[Union[datetime, str]] = None
    estado: Optional[EstadoEnum] = None
    prioridad: Optional[PrioridadEnum] = None
    asignar: Optional[str] = None
    columna: Optional[int] = Field(None, ge=1, le=4, description="Filtrar por columna")
    leido: Optional[bool] = Field(None, description="Filtrar por leido (true/false)")
    q: Optional[str] = Field(None, description="Busqueda libre por titulo o descripcion")


class TicketResponse(BaseModel):
    id: PydanticObjectId
    identificador: str
    titulo: str
    descripcion: str
    correo: EmailStr
    prioridad: PrioridadEnum
    estado: EstadoEnum
    asignar: Optional[str]
    imagenes: List[str]
    fecha_creacion: datetime
    fecha_edicion: Optional[datetime]
    columna: int = Field(default=1)
    leido: bool = Field(default=False)
    frecuencia: Optional[Frecuencia] = None

    @field_serializer("fecha_creacion", "fecha_edicion", when_used="json")
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )


class TicketPagedResponse(BaseModel):
    """Respuesta paginada para el listado de tickets."""
    total: int = Field(..., description="Total de tickets que coinciden con los filtros (sin paginacion)")
    skip: int = Field(..., description="Registros omitidos (offset)")
    limit: int = Field(..., description="Limite de registros por pagina")
    items: List[TicketResponse] = Field(..., description="Lista de tickets de la pagina actual")
