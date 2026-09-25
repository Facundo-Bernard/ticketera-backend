from fastapi import APIRouter, status
from .schema import PushSubscriptionCreate, VapidPublicKeyResponse, PushTestRequest
from .service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notificaciones"])

@router.get("/vapid-public-key", response_model=VapidPublicKeyResponse)
async def get_vapid_public_key():
    return {"public_key": NotificationService.get_public_key()}

@router.post("/subscribe", status_code=status.HTTP_201_CREATED)
async def subscribe(body: PushSubscriptionCreate):
    sub = await NotificationService.subscribe(
        endpoint=body.endpoint,
        p256dh=body.keys.p256dh,
        auth=body.keys.auth,
        usuario_email=body.usuario_email
    )
    return {"status": "ok", "id": str(sub.id)}

@router.post("/unsubscribe")
async def unsubscribe(endpoint: str):
    success = await NotificationService.unsubscribe(endpoint)
    return {"status": "ok", "deleted": success}

@router.post("/test")
async def test_notification(body: PushTestRequest):
    payload = {
        "title": body.title,
        "body": body.body,
        "url": body.url or "/"
    }
    sent = await NotificationService.broadcast(payload, target_email=body.usuario_email)
    return {"status": "ok", "sent_to_devices": sent}
