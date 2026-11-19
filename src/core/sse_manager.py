import asyncio
from collections import deque
import logging
from typing import Any, Deque, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class SSEManager:
    """
    Gestor de conexiones en tiempo real para Server-Sent Events (SSE).
    Mantiene colas asíncronas para cada cliente conectado y un buffer circular
    para reenviar eventos perdidos mediante Last-Event-ID al reconectar.
    """

    def __init__(self, history_limit: int = 200):
        self.listeners: Set[asyncio.Queue] = set()
        self._history: Deque[Dict[str, Any]] = deque(maxlen=history_limit)
        self._next_event_id: int = 1

    async def subscribe(self, last_event_id: Optional[int] = None) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        if last_event_id is not None and last_event_id > 0:
            for item in self._history:
                if int(item["id"]) > last_event_id:
                    await queue.put(item)
        self.listeners.add(queue)
        logger.debug(f"[SSE] Nuevo suscriptor conectado. Total activos: {len(self.listeners)}")
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self.listeners.discard(queue)
        logger.debug(f"[SSE] Suscriptor desconectado. Total activos: {len(self.listeners)}")

    async def broadcast(self, event: str, data: Dict[str, Any]) -> None:
        """Envía un evento con ID incremental a todas las pantallas conectadas."""
        event_id = self._next_event_id
        self._next_event_id += 1

        payload: Dict[str, Any] = {
            "id": event_id,
            "event": event,
            "data": data,
        }
        self._history.append(payload)

        if not self.listeners:
            return

        for queue in list(self.listeners):
            try:
                await queue.put(payload)
            except Exception as e:
                logger.warning(f"[SSE] Error al enviar mensaje a listener: {e}")

    def clear_history(self) -> None:
        """Limpia el historial de eventos en memoria (útil para tests)."""
        self._history.clear()
        self._next_event_id = 1


sse_manager = SSEManager()
