from typing import Optional
from pydantic import BaseModel

class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str

class PushSubscriptionCreate(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeys
    usuario_email: Optional[str] = None

class VapidPublicKeyResponse(BaseModel):
    public_key: str

class PushTestRequest(BaseModel):
    title: Optional[str] = "🔔 Prueba de Notificación"
    body: Optional[str] = "Las notificaciones push de Tickets Coopya funcionan correctamente."
    url: Optional[str] = "/"
    usuario_email: Optional[str] = None
