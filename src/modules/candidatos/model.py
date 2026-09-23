from datetime import datetime, timezone
from typing import List, Optional
from beanie import Document, Indexed
from pydantic import BaseModel, Field, EmailStr

class ProductoSeleccionado(BaseModel):
    familia: str
    plan: str
    monto: float
    plazoMeses: int

class Candidato(Document):
    """
    Documento Beanie para la colección 'candidatos' (puente temporal).
    Almacena datos personales, laborales y producto crediticio seleccionado.
    """
    nombreCompleto: str = Field(..., min_length=2, max_length=150)
    dni: Indexed(str)
    email: EmailStr
    telefono: str = Field(..., min_length=6, max_length=30)
    direccion: str = Field(..., min_length=3, max_length=250)
    genero: str
    edad: int = Field(..., ge=18, le=120)
    situacionLaboral: str
    ingresoMensual: float = Field(..., ge=0)
    moneda: str = Field(default="ARS")
    bancosSeleccionados: List[str] = Field(default_factory=list)
    productoSeleccionado: ProductoSeleccionado
    origen: str = Field(default="web")
    fechaCreacion: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "candidatos"
        indexes = [
            "dni",
            "email",
            "-fechaCreacion"
        ]
