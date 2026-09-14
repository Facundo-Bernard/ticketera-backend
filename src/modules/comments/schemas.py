from pydantic import BaseModel, Field, ConfigDict, field_serializer
from typing import Optional, Union, List
from datetime import datetime, timezone
from beanie import PydanticObjectId

class CommentFilter(BaseModel):
    autor: Optional[str] = Field(None, description="Filtrar por nombre o correo del autor")
    fecha_desde: Optional[Union[datetime, str]] = Field(None, description="Filtrar desde fecha (YYYY-MM-DD o ISO)")
    fecha_hasta: Optional[Union[datetime, str]] = Field(None, description="Filtrar hasta fecha (YYYY-MM-DD o ISO)")

class CommentCreate(BaseModel):
    autor: str = Field(..., min_length=2, max_length=100, description="Nombre o correo del autor del comentario")
    mensaje: str = Field(..., min_length=1, max_length=2000, description="Contenido del comentario")

class CommentUpdate(BaseModel):
    mensaje: Optional[str] = Field(None, min_length=1, max_length=2000)

class CommentResponse(BaseModel):
    id: str
    ticket_id: PydanticObjectId
    autor: str
    mensaje: str
    fecha_creacion: datetime

    @field_serializer("fecha_creacion", when_used="json")
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
