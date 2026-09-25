from datetime import datetime, timezone
from typing import Optional
from beanie import Document, Indexed
from pydantic import Field

class PushSubscription(Document):
    endpoint: Indexed(str, unique=True)
    p256dh: str
    auth: str
    usuario_email: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "push_subscriptions"
        indexes = [
            "endpoint",
            "usuario_email",
        ]
