from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional, List, Union
from datetime import datetime
from beanie import PydanticObjectId
from ..models.ticket_model import PrioridadEnum, EstadoEnum

class TicketCreate(BaseModel):
    titulo: str = Field(..., min_length=3, max_length=150, description="Título conciso del ticket")
    descripcion: str = Field(..., description="Descripción detallada del problema")
    correo: EmailStr = Field(..., description="Correo de contacto del solicitante")
    prioridad: Optional[PrioridadEnum] = Field(default=PrioridadEnum.MEDIA, description="Prioridad del ticket")
    asignar: Optional[str] = Field(default=None, description="Usuario o técnico asignado")
    imagenes: Optional[List[str]] = Field(default_factory=list, description="Lista opcional de IDs o URLs de imágenes")

class TicketUpdate(BaseModel):
    titulo: Optional[str] = Field(None, min_length=3, max_length=150)
    descripcion: Optional[str] = None
    correo: Optional[EmailStr] = None
    prioridad: Optional[PrioridadEnum] = None
    estado: Optional[EstadoEnum] = None
    asignar: Optional[str] = None
    imagenes: Optional[List[str]] = None

class TicketFilter(BaseModel):
    fecha_desde: Optional[Union[datetime, str]] = None
    fecha_hasta: Optional[Union[datetime, str]] = None
    estado: Optional[EstadoEnum] = None
    prioridad: Optional[PrioridadEnum] = None
    asignar: Optional[str] = None

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

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )
