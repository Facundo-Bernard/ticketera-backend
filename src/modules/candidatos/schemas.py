from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_serializer
from typing import List, Optional
from datetime import datetime, timezone
from beanie import PydanticObjectId

class ProductoSeleccionadoSchema(BaseModel):
    familia: str = Field(..., description="Familia del producto financiero")
    plan: str = Field(..., description="Identificador o código del plan")
    monto: float = Field(..., ge=0, description="Monto solicitado o aprobado")
    plazoMeses: int = Field(..., ge=1, le=120, description="Plazo en meses")

class CandidatoCreate(BaseModel):
    nombreCompleto: str = Field(..., min_length=2, max_length=150, description="Nombre y apellido completo")
    dni: str = Field(..., min_length=6, max_length=20, description="Número de documento")
    email: EmailStr = Field(..., description="Correo electrónico de contacto")
    telefono: str = Field(..., min_length=6, max_length=30, description="Teléfono de contacto")
    direccion: str = Field(..., min_length=3, max_length=250, description="Dirección o domicilio")
    genero: str = Field(..., description="Género del candidato")
    edad: int = Field(..., ge=18, le=120, description="Edad del candidato")
    situacionLaboral: str = Field(..., description="Situación laboral actual")
    ingresoMensual: float = Field(..., ge=0, description="Ingreso neto mensual")
    moneda: Optional[str] = Field(default="ARS", description="Moneda del ingreso y crédito")
    bancosSeleccionados: Optional[List[str]] = Field(default_factory=list, description="Lista de bancos seleccionados")
    productoSeleccionado: ProductoSeleccionadoSchema = Field(..., description="Detalle del producto crediticio")
    origen: Optional[str] = Field(default="web", description="Canal de origen de la postulación")
    papeleria: Optional[str] = Field(default=None, description="URL o identificador de papelería en GridFS")

class CandidatoResponse(BaseModel):
    id: PydanticObjectId
    nombreCompleto: str
    dni: str
    email: EmailStr
    telefono: str
    direccion: str
    genero: str
    edad: int
    situacionLaboral: str
    ingresoMensual: float
    moneda: str
    bancosSeleccionados: List[str]
    productoSeleccionado: ProductoSeleccionadoSchema
    origen: str
    papeleria: Optional[str] = None
    fechaCreacion: datetime

    @field_serializer("fechaCreacion", when_used="json")
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
