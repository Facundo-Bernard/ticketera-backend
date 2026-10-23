from fastapi import APIRouter, Depends, status, Response, Request
from .schemas import UserRegister, UserLogin, UserResponse, TokenResponse
from .service import AuthService
from .dependencies import get_current_user
from .model import User
from ...config.settings import settings

router = APIRouter(prefix="/auth", tags=["Autenticación"])

@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Iniciar sesión y obtener token JWT"
)
async def login(
    credentials: UserLogin,
    response: Response,
    request: Request,
    service: AuthService = Depends()
):
    """
    Valida credenciales (email y contraseña), retorna el access_token y emite la cookie segura HttpOnly 'coopya_auth_token'.
    """
    token_data = await service.authenticate(credentials)
    
    # Determinar si la conexión es HTTPS (directa o detrás de Caddy/Nginx)
    is_secure = (
        settings.COOKIE_SECURE
        or request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto") == "https"
    )

    response.set_cookie(
        key="coopya_auth_token",
        value=token_data.access_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )
    return token_data

@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Cerrar sesión y limpiar cookie HttpOnly"
)
async def logout(response: Response):
    """
    Elimina la cookie de sesión HttpOnly del navegador.
    """
    response.delete_cookie(key="coopya_auth_token", path="/")
    return {"status": "ok", "message": "Sesión cerrada exitosamente"}

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
