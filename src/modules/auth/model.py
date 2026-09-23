from datetime import datetime, timezone
from typing import Optional
from beanie import Document, Indexed
from pydantic import Field, EmailStr

class User(Document):
    """
    Documento Beanie para la colección 'usuarios'.
    Almacena los operadores y administradores del dashboard con acceso autenticado.
    """
    email: Indexed(EmailStr, unique=True)
    nombre: str = Field(..., min_length=2, max_length=120)
    hashed_password: str
    rol: str = Field(default="operador", description="Rol del usuario ('admin', 'operador')")
    activo: bool = Field(default=True, description="Indica si el usuario puede iniciar sesión")
    fechaCreacion: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ultimoLogin: Optional[datetime] = None

    class Settings:
        name = "usuarios"
        indexes = [
            "email",
            "rol",
        ]
