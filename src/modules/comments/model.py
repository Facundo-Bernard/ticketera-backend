from datetime import datetime, timezone
from typing import List, Optional
from beanie import Document, Indexed, PydanticObjectId
from pydantic import BaseModel, Field

class CommentItem(BaseModel):
    id: str = Field(default_factory=lambda: str(PydanticObjectId()))
    autor: str = Field(..., min_length=2, max_length=100, description="Nombre o correo de quien comenta")
    mensaje: str = Field(..., min_length=1, max_length=2000, description="Texto del comentario")
    fecha_creacion: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CommentBucket(Document):
    """
    Patrón Bucket (Document-per-Thread):
    Agrupa todos los comentarios pertenecientes a un ticket en un único documento contenedor.
    Permite lecturas O(1) con proyección $slice de MongoDB para paginar de 10 en 10.
    """
    ticket_id: Indexed(PydanticObjectId, unique=True)
    total: int = Field(default=0, description="Conteo total de comentarios en el bucket")
    comentarios: List[CommentItem] = Field(default_factory=list, description="Array de comentarios del ticket")

    class Settings:
        name = "comment_buckets"
        indexes = [
            "ticket_id"
        ]
