from datetime import datetime, timezone
from typing import List, Optional
from fastapi import Depends
from beanie import PydanticObjectId
from ...config.settings import settings
from ...core.exceptions import BadRequestException, UnauthorizedException, NotFoundException
from .model import User
from .schemas import UserRegister, UserUpdate, UserLogin, TokenResponse, UserResponse
from .security import hash_password, verify_password, create_access_token
from .repository import UserRepository

class AuthService:
    """
    Servicio de lógica de negocio para autenticación y gestión de usuarios.
    """
    def __init__(self, repository: UserRepository = Depends()):
        self.repository = repository

    async def register_user(self, user_in: UserRegister) -> User:
        """
        Registra un nuevo usuario operador o administrador.
        Lanza BadRequestException si el email ya se encuentra en uso.
        """
        clean_email = user_in.email.lower().strip()
        existing = await self.repository.get_by_email(clean_email)
        if existing:
            raise BadRequestException("Ya existe un usuario registrado con este correo electrónico")

        hashed_pwd = hash_password(user_in.password)
        user = User(
            email=clean_email,
            nombre=user_in.nombre.strip(),
            hashed_password=hashed_pwd,
            rol=user_in.rol,
            activo=True
        )
        return await user.insert()

    async def authenticate(self, credentials: UserLogin) -> TokenResponse:
        """
        Autentica credenciales (email y contraseña) y emite un JWT firmado.
        Lanza UnauthorizedException si las credenciales son incorrectas o la cuenta está inactiva.
        """
        clean_email = credentials.email.lower().strip()
        user = await self.repository.get_by_email(clean_email)
        if not user or not verify_password(credentials.password, user.hashed_password):
            raise UnauthorizedException("Correo electrónico o contraseña incorrectos")

        if not user.activo:
            raise UnauthorizedException("La cuenta de usuario se encuentra desactivada")

        # Actualizar fecha de último login
        user.ultimoLogin = datetime.now(timezone.utc)
        await user.save()

        # Generar JWT con id, email y rol
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "rol": user.rol
        }
        token = create_access_token(token_data)

        user_resp = UserResponse.model_validate(user)
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=user_resp
        )

    async def get_user_by_id(self, user_id: PydanticObjectId) -> User:
        """
        Obtiene un usuario por su ID de MongoDB o lanza NotFoundException si no existe.
        """
        user = await self.repository.get(user_id)
        if not user:
            raise NotFoundException("Usuario no encontrado")
        return user

    async def list_users(self) -> List[User]:
        """Lista todos los operadores y administradores registrados."""
        return await self.repository.list_all_ordered()

    async def update_user(
        self,
        user_id: PydanticObjectId,
        data: UserUpdate,
        acting_admin: User,
    ) -> User:
        """Actualiza nombre, rol, estado o contraseña de un usuario protegiendo al admin actual/maestro."""
        user = await self.get_user_by_id(user_id)
        master_email = settings.MASTER_ADMIN_EMAIL.strip().lower()
        is_self = user.id == acting_admin.id
        is_master = user.email.lower() == master_email

        if data.activo is False and (is_self or is_master):
            raise BadRequestException("No podés desactivar tu propia cuenta ni la cuenta administrativa principal.")

        if data.rol is not None and data.rol != "admin" and (is_self or is_master):
            raise BadRequestException("No podés quitar el rol de administrador a tu cuenta ni a la cuenta principal.")

        if data.nombre is not None:
            clean_name = data.nombre.strip()
            if len(clean_name) < 2:
                raise BadRequestException("El nombre debe tener al menos 2 caracteres.")
            user.nombre = clean_name

        if data.rol is not None:
            user.rol = data.rol

        if data.activo is not None:
            user.activo = data.activo

        if data.password:
            user.hashed_password = hash_password(data.password)

        await user.save()
        return user

    async def delete_user(self, user_id: PydanticObjectId, acting_admin: User) -> None:
        """Elimina un operador protegiendo la cuenta propia y la cuenta maestra."""
        user = await self.get_user_by_id(user_id)
        master_email = settings.MASTER_ADMIN_EMAIL.strip().lower()

        if user.id == acting_admin.id:
            raise BadRequestException("No podés eliminar tu propia cuenta mientras estás autenticado.")
        if user.email.lower() == master_email:
            raise BadRequestException("No se puede eliminar la cuenta administrativa principal.")

        await self.repository.delete(user_id)
