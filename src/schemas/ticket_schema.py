from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_serializer, field_validator, model_validator
from typing import Optional, List, Union
from datetime import datetime, timezone
from beanie import PydanticObjectId
from ..models.ticket_model import PrioridadEnum, EstadoEnum, Frecuencia

class TicketBase(BaseModel):
    """Base class con validadores compartidos para todos los schemas de tickets."""
    
    @field_validator('titulo')
    @classmethod
    def validate_titulo(cls, v: Optional[str]) -> Optional[str]:
        """Valida que el título no esté vacío después de eliminar espacios."""
        if v is not None and not v.strip():
            raise ValueError('El título no puede estar vacío o contener solo espacios')
        return v

    @field_validator('imagenes')
    @classmethod
    def validate_imagenes(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Valida la lista de imágenes para prevenir DoS, XSS y datos inválidos."""
        if v:
            if len(v) > 10:
                raise ValueError('Máximo 10 imágenes permitidas por ticket')
            
            for url in v:
                if not url.strip():
                    raise ValueError('Las URLs de imagen no pueden estar vacías')
                
                # Permitir URLs internas del sistema (/api/v1/files/)
                if url.startswith('/api/v1/files/'):
                    continue
                
                # Permitir solo http/https externos
                if not (url.startswith('http://') or url.startswith('https://')):
                    raise ValueError('Solo URLs http/https o internas /api/v1/files/ permitidas')
                
                # Rechazar patrones peligrosos (XSS, SSRF, path traversal)
                dangerous_patterns = ['javascript:', 'data:', 'file:', 'vbscript:', '../../', '..\\']
                if any(dangerous in url.lower() for dangerous in dangerous_patterns):
                    raise ValueError('Formato de URL no permitido por seguridad')
        
        return v

    @model_validator(mode='after')
    def validate_consistencia(cls, model: 'TicketBase') -> 'TicketBase':
        """Valida la consistencia entre campos relacionados."""
        if model.frecuencia:
            if model.frecuencia.numero < 1:
                raise ValueError('El número de frecuencia debe ser al menos 1')
        return model

    model_config = ConfigDict(
        extra='forbid',  # Rechaza campos adicionales no especificados
        str_strip_whitespace=True  # Elimina espacios en blanco de strings automáticamente
    )

class TicketCreate(TicketBase):
    titulo: str = Field(..., min_length=3, max_length=150, description="Título conciso del ticket")
    descripcion: str = Field(..., min_length=10, max_length=5000, description="Descripción detallada del problema")
    correo: EmailStr = Field(..., description="Correo de contacto del solicitante")
    prioridad: Optional[PrioridadEnum] = Field(default=PrioridadEnum.MEDIA, description="Prioridad del ticket")
    asignar: Optional[str] = Field(default=None, min_length=1, max_length=100, description="Usuario o técnico asignado")
    imagenes: Optional[List[str]] = Field(default_factory=list, description="Lista opcional de IDs o URLs de imágenes")
    columna: Optional[int] = Field(default=1, ge=1, le=4, description="ID numérico de la columna")
    frecuencia: Optional[Frecuencia] = Field(default=None, description="Frecuencia periódica si aplica")

class TicketUpdate(TicketBase):
    titulo: Optional[str] = Field(None, min_length=3, max_length=150)
    descripcion: Optional[str] = Field(None, min_length=10, max_length=5000)
    correo: Optional[EmailStr] = None
    prioridad: Optional[PrioridadEnum] = None
    estado: Optional[EstadoEnum] = None
    asignar: Optional[str] = Field(None, min_length=1, max_length=100)
    imagenes: Optional[List[str]] = None
    columna: Optional[int] = Field(None, ge=1, le=4, description="ID numérico de la columna")
    leido: Optional[bool] = Field(None, description="Marcar como leído o no leído")
    frecuencia: Optional[Frecuencia] = Field(None, description="Actualizar frecuencia periódica")

class TicketFilter(BaseModel):
    fecha_desde: Optional[Union[datetime, str]] = None
    fecha_hasta: Optional[Union[datetime, str]] = None
    estado: Optional[EstadoEnum] = None
    prioridad: Optional[PrioridadEnum] = None
    asignar: Optional[str] = None
    columna: Optional[int] = Field(None, ge=1, le=4, description="Filtrar por columna")
    leido: Optional[bool] = Field(None, description="Filtrar por leído (true/false)")

    @field_validator('fecha_desde', 'fecha_hasta', mode='before')
    @classmethod
    def validate_fechas(cls, v: Optional[Union[datetime, str]]) -> Optional[datetime]:
        """Valida y parsea fechas strings para prevenir errores de parsing."""
        if v is None:
            return None
        
        if isinstance(v, datetime):
            return v
        
        try:
            from dateutil.parser import parse
            return parse(v)
        except Exception:
            raise ValueError('Formato de fecha inválido. Use: YYYY-MM-DD o YYYY-MM-DDTHH:MM:SS')

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
