from fastapi import APIRouter, Depends, status
from .schema import PushSubscriptionCreate, VapidPublicKeyResponse, PushTestRequest
from .service import NotificationService
from ..auth import get_current_user, User

router = APIRouter(prefix="/notifications", tags=["Notificaciones"])

@router.get("/vapid-public-key", response_model=VapidPublicKeyResponse)
async def get_vapid_public_key():
    return {"public_key": NotificationService.get_public_key()}

@router.post("/subscribe", status_code=status.HTTP_201_CREATED)
async def subscribe(
    body: PushSubscriptionCreate,
    current_user: User = Depends(get_current_user)
):
    target_email = (
        body.usuario_email
        if current_user.rol == "admin" and body.usuario_email
        else current_user.email
    )
    sub = await NotificationService.subscribe(
        endpoint=body.endpoint,
        p256dh=body.keys.p256dh,
        auth=body.keys.auth,
        usuario_email=target_email
    )
    return {"status": "ok", "id": str(sub.id)}

@router.post("/unsubscribe")
async def unsubscribe(
    endpoint: str,
    current_user: User = Depends(get_current_user)
):
    success = await NotificationService.unsubscribe(endpoint)
    return {"status": "ok", "deleted": success}

@router.post("/test")
async def test_notification(
    body: PushTestRequest,
    current_user: User = Depends(get_current_user)
):
    payload = {
        "title": body.title,
        "body": body.body,
        "url": body.url or "/"
    }
    # Solo administradores pueden enviar push de prueba a otro correo o broadcast global
    target_email = (
        body.usuario_email
        if current_user.rol == "admin"
        else current_user.email
    )
    sent = await NotificationService.broadcast(payload, target_email=target_email)
    return {"status": "ok", "sent_to_devices": sent}
