from fastapi import APIRouter, Depends, status
from .schemas import UserRegister, UserLogin, UserResponse, TokenResponse
from .service import AuthService
from .dependencies import get_current_user
from .model import User

router = APIRouter(prefix="/auth", tags=["Autenticación"])

# Endpoint deshabilitado temporalmente a pedido
# @router.post(
#     "/register",
#     response_model=UserResponse,
#     status_code=status.HTTP_201_CREATED,
#     summary="Registrar un nuevo operador o administrador"
# )
# async def register(
#     user_in: UserRegister,
#     service: AuthService = Depends()
# ):
#     """
#     Registra una nueva cuenta de usuario en la colección 'usuarios' con contraseña hasheada en bcrypt.
#     """
#     user = await service.register_user(user_in)
#     return user

@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Iniciar sesión y obtener token JWT"
)
async def login(
    credentials: UserLogin,
    service: AuthService = Depends()
):
    """
    Valida credenciales (email y contraseña) y retorna el access_token JWT junto con el perfil del usuario.
    """
    return await service.authenticate(credentials)

@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener perfil del usuario autenticado"
)
async def get_me(
    current_user: User = Depends(get_current_user)
):
    """
    Retorna la información del usuario autenticado actualmente a partir de su Bearer Token.
    """
    return current_user
