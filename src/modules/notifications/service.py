import json
import logging
from typing import Optional, Dict, Any
from pywebpush import webpush, WebPushException
from .model import PushSubscription
from ...config.settings import settings

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    def get_public_key() -> str:
        return settings.VAPID_PUBLIC_KEY

    @staticmethod
    async def subscribe(endpoint: str, p256dh: str, auth: str, usuario_email: Optional[str] = None) -> PushSubscription:
        existing = await PushSubscription.find_one(PushSubscription.endpoint == endpoint)
        if existing:
            existing.p256dh = p256dh
            existing.auth = auth
            if usuario_email:
                existing.usuario_email = usuario_email.lower().strip()
            await existing.save()
            return existing
        
        sub = PushSubscription(
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            usuario_email=usuario_email.lower().strip() if usuario_email else None
        )
        await sub.insert()
        return sub

    @staticmethod
    async def unsubscribe(endpoint: str) -> bool:
        sub = await PushSubscription.find_one(PushSubscription.endpoint == endpoint)
        if sub:
            await sub.delete()
            return True
        return False

    @staticmethod
    async def send_notification_to_sub(sub: PushSubscription, payload: Dict[str, Any]) -> bool:
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh,
                "auth": sub.auth
            }
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": f"mailto:{settings.VAPID_CLAIMS_EMAIL}"}
            )
            return True
        except WebPushException as ex:
            logger.warning(f"Error enviando Web Push a {sub.endpoint}: {ex}")
            if ex.response and ex.response.status_code in [404, 410]:
                await sub.delete()
                logger.info(f"Suscripcion expirada eliminada: {sub.endpoint}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado al enviar push: {e}")
            return False

    @staticmethod
    async def broadcast(payload: Dict[str, Any], target_email: Optional[str] = None) -> int:
        if target_email:
            subs = await PushSubscription.find(PushSubscription.usuario_email == target_email.lower().strip()).to_list()
        else:
            subs = await PushSubscription.find().to_list()
        
        success_count = 0
        for sub in subs:
            sent = await NotificationService.send_notification_to_sub(sub, payload)
            if sent:
                success_count += 1
        return success_count
