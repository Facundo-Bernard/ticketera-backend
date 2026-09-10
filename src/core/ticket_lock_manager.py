from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from pydantic import BaseModel


class LockInfo(BaseModel):
    ticket_id: str
    usuario: str
    expira_en: datetime


class TicketLockManager:
    """
    Gestor en memoria de bloqueos de edición de tickets con expiración automática (TTL).
    Permite evitar colisiones de edición concurrente entre múltiples operadores.
    """
    def __init__(self, ttl_seconds: int = 180):
        self._locks: Dict[str, LockInfo] = {}
        self.ttl_seconds = ttl_seconds

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def is_locked(self, ticket_id: str) -> Optional[LockInfo]:
        """Retorna la info del lock si está activo y no expiró. Limpia locks viejos."""
        t_id = str(ticket_id)
        lock = self._locks.get(t_id)
        if not lock:
            return None
        
        # Verificar si expiró
        if self._now() > lock.expira_en:
            del self._locks[t_id]
            return None
        
        return lock

    def acquire_lock(self, ticket_id: str, usuario: str) -> Tuple[bool, Optional[LockInfo]]:
        """
        Intenta adquirir el bloqueo para un ticket.
        Retorna (True, lock_info) si lo adquirió o ya era del mismo usuario.
        Retorna (False, lock_info_actual) si está bloqueado por otro usuario activo.
        """
        t_id = str(ticket_id)
        current_lock = self.is_locked(t_id)

        # Si está bloqueado por otro usuario activo
        if current_lock and current_lock.usuario.lower() != usuario.lower():
            return False, current_lock

        # Asignar o renovar bloqueo
        new_lock = LockInfo(
            ticket_id=t_id,
            usuario=usuario,
            expira_en=self._now() + timedelta(seconds=self.ttl_seconds)
        )
        self._locks[t_id] = new_lock
        return True, new_lock

    def release_lock(self, ticket_id: str, usuario: Optional[str] = None) -> bool:
        """
        Libera el bloqueo de un ticket.
        Si se pasa usuario, solo lo libera si coincide con el poseedor actual (o si ya expiró).
        """
        t_id = str(ticket_id)
        current_lock = self.is_locked(t_id)
        if not current_lock:
            self._locks.pop(t_id, None)
            return True

        if usuario and current_lock.usuario.lower() != usuario.lower():
            return False

        self._locks.pop(t_id, None)
        return True

    def clear(self) -> None:
        """Limpia todos los bloqueos en memoria (útil para testing)."""
        self._locks.clear()


ticket_lock_manager = TicketLockManager(ttl_seconds=180)
