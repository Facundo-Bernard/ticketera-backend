from datetime import datetime, timezone
from typing import Optional
from beanie import PydanticObjectId
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_serializer

class UserRegister(BaseModel):
    """
    Esquema para dar de alta un nuevo usuario operador o administrador.
    """
    email: EmailStr = Field(..., description="Correo electrónico único del usuario")
    password: str = Field(..., min_length=3, max_length=100, description="Contraseña en texto plano")
    nombre: str = Field(..., min_length=2, max_length=120, description="Nombre completo del usuario")
    rol: str = Field(default="operador", pattern="^(admin|operador)$", description="Rol ('admin' u 'operador')")

class UserLogin(BaseModel):
    """
    Esquema de credenciales para iniciar sesión.
    """
    email: EmailStr = Field(..., description="Correo electrónico registrado")
    password: str = Field(..., description="Contraseña")

class UserResponse(BaseModel):
    """
    Esquema de respuesta pública de un usuario (excluye contraseña hasheada).
    """
    id: PydanticObjectId
    email: EmailStr
    nombre: str
    rol: str
    activo: bool
    fechaCreacion: datetime
    ultimoLogin: Optional[datetime] = None

    @field_serializer("fechaCreacion", "ultimoLogin", when_used="json")
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

class TokenResponse(BaseModel):
    """
    Esquema de respuesta tras autenticación exitosa.
    """
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
