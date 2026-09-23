from typing import Optional
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from beanie import PydanticObjectId
from ...core.exceptions import UnauthorizedException, ForbiddenException
from .model import User
from .security import decode_access_token
from .repository import UserRepository

# Esquema de seguridad Bearer para Swagger UI y validación de encabezados HTTP
bearer_scheme = HTTPBearer(auto_error=True)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    repository: UserRepository = Depends()
) -> User:
    """
    Dependencia de FastAPI que valida el token JWT Bearer del encabezado Authorization.
    Verifica firma, expiración y vigencia del usuario en MongoDB.
    """
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except Exception as e:
        raise UnauthorizedException(f"Token de autenticación inválido o expirado: {str(e)}")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedException("El token no contiene un identificador de usuario válido")

    try:
        user_id = PydanticObjectId(user_id_str)
    except Exception:
        raise UnauthorizedException("Identificador de usuario con formato inválido en el token")

    user = await repository.get(user_id)
    if not user:
        raise UnauthorizedException("El usuario asociado al token ya no existe")

    if not user.activo:
        raise UnauthorizedException("La cuenta de usuario se encuentra inactiva")

    return user

async def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependencia que valida que el usuario autenticado tenga rol de 'admin'.
    """
    if current_user.rol != "admin":
        raise ForbiddenException("Acceso restringido a administradores del sistema")
    return current_user
