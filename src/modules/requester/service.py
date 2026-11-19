from datetime import datetime, timedelta, timezone
import re
import secrets
from typing import Any, Dict, List, Optional
from beanie import PydanticObjectId
from ...core.exceptions import BadRequestException, NotFoundException
from ...core.sse_manager import sse_manager
from ...models.ticket_model import Ticket
from .model import RequesterAccessCode
from .schemas import (
    AccessCodeItemResponse,
    RequesterRequestCodeResponse,
    RequesterTicketResponse,
)
from .security import RequesterContext


CODE_TTL_MINUTES = 15
SELF_REQUEST_COOLDOWN_SECONDS = 60
MAX_FAILED_ATTEMPTS = 5
MAX_REQUESTER_TICKETS = 200


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _generate_six_digit_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _build_requester_ticket_filter(ctx: RequesterContext) -> Optional[Dict[str, Any]]:
    # Si hay una cuenta vinculada por código temporal, mostrar estrictamente el historial de ese correo
    # para que todos los dispositivos/navegadores vinculados vean exactamente los mismos tickets.
    if ctx.email:
        return {
            "correo": {"$regex": f"^{re.escape(ctx.email.strip())}$", "$options": "i"}
        }

    valid_object_ids: List[PydanticObjectId] = []
    for raw_id in ctx.local_ticket_ids:
        try:
            valid_object_ids.append(PydanticObjectId(raw_id))
        except Exception:
            continue

    if valid_object_ids:
        return {"_id": {"$in": valid_object_ids}}

    return None


def sanitize_ticket_for_requester(ticket_data: Dict[str, Any]) -> Dict[str, Any]:
    """Proyecta estrictamente los campos permitidos para eventos SSE del solicitante."""
    return {
        "id": str(ticket_data.get("id", "")),
        "identificador": str(ticket_data.get("identificador", "")),
        "titulo": str(ticket_data.get("titulo", "")),
        "descripcion": str(ticket_data.get("descripcion", "")),
        "estado": ticket_data.get("estado", "abierto"),
        "imagenes": list(ticket_data.get("imagenes") or []),
        "fecha_creacion": ticket_data.get("fecha_creacion"),
        "fecha_edicion": ticket_data.get("fecha_edicion"),
    }


class RequesterService:
    async def _expire_stale_pending(self, now: datetime) -> None:
        collection = RequesterAccessCode.get_pymongo_collection()
        await collection.update_many(
            {"estado": "pendiente", "expira_en": {"$lte": now}},
            {"$set": {"estado": "expirado"}},
        )

    async def _revoke_pending_for_email(self, correo: str) -> None:
        collection = RequesterAccessCode.get_pymongo_collection()
        await collection.update_many(
            {"correo": correo, "estado": "pendiente"},
            {"$set": {"estado": "revocado"}},
        )

    async def _broadcast_code_event(self, correo: str, action: str) -> None:
        try:
            await sse_manager.broadcast(
                "codigo_acceso_actualizado",
                {"correo": correo, "action": action},
            )
        except Exception:
            pass

    async def request_code(self, correo: str) -> RequesterRequestCodeResponse:
        normalized_email = str(correo).strip().lower()
        now = datetime.now(timezone.utc)
        await self._expire_stale_pending(now)

        latest_pending = await (
            RequesterAccessCode.find(
                RequesterAccessCode.correo == normalized_email,
                RequesterAccessCode.estado == "pendiente",
            )
            .sort("-creado_en")
            .first_or_none()
        )

        if latest_pending and _ensure_utc(latest_pending.expira_en) > now:
            elapsed = (now - _ensure_utc(latest_pending.creado_en)).total_seconds()
            if elapsed < SELF_REQUEST_COOLDOWN_SECONDS:
                return RequesterRequestCodeResponse(
                    message="Ya tenés una solicitud activa. Pedile el código temporal de 6 dígitos al equipo de Soporte.",
                    expira_en=_ensure_utc(latest_pending.expira_en),
                )

        await self._revoke_pending_for_email(normalized_email)

        expires_at = now + timedelta(minutes=CODE_TTL_MINUTES)
        doc = RequesterAccessCode(
            correo=normalized_email,
            codigo=_generate_six_digit_code(),
            estado="pendiente",
            solicitado_por="usuario",
            generado_por=None,
            creado_en=now,
            expira_en=expires_at,
        )
        await doc.insert()
        await self._broadcast_code_event(normalized_email, "requested")

        return RequesterRequestCodeResponse(
            message="Solicitud registrada. Pedile al equipo de Soporte tu código temporal (válido por 15 minutos).",
            expira_en=expires_at,
        )

    async def generate_code_for_operator(
        self,
        correo: str,
        operator_email: str,
    ) -> AccessCodeItemResponse:
        normalized_email = str(correo).strip().lower()
        now = datetime.now(timezone.utc)
        await self._expire_stale_pending(now)
        await self._revoke_pending_for_email(normalized_email)

        expires_at = now + timedelta(minutes=CODE_TTL_MINUTES)
        doc = RequesterAccessCode(
            correo=normalized_email,
            codigo=_generate_six_digit_code(),
            estado="pendiente",
            solicitado_por="operador",
            generado_por=operator_email.strip().lower(),
            creado_en=now,
            expira_en=expires_at,
        )
        await doc.insert()
        await self._broadcast_code_event(normalized_email, "generated")
        return AccessCodeItemResponse.model_validate(doc)

    async def verify_code(self, correo: str, raw_codigo: str) -> str:
        normalized_email = str(correo).strip().lower()
        clean_code = re.sub(r"[\s-]+", "", raw_codigo or "")
        if not clean_code:
            raise BadRequestException("Ingresá un código válido.")

        now = datetime.now(timezone.utc)
        pending = await (
            RequesterAccessCode.find(
                RequesterAccessCode.correo == normalized_email,
                RequesterAccessCode.estado == "pendiente",
            )
            .sort("-creado_en")
            .first_or_none()
        )

        if not pending:
            raise BadRequestException(
                "No hay un código activo para ese correo. Solicitá uno nuevo al equipo de Soporte."
            )

        if _ensure_utc(pending.expira_en) <= now:
            pending.estado = "expirado"
            await pending.save()
            await self._broadcast_code_event(normalized_email, "expired")
            raise BadRequestException(
                "El código temporal venció (15 min). Solicitá uno nuevo al equipo de Soporte."
            )

        if pending.codigo != clean_code:
            next_attempts = pending.intentos_fallidos + 1
            pending.intentos_fallidos = next_attempts
            if next_attempts >= MAX_FAILED_ATTEMPTS:
                pending.estado = "revocado"
                await pending.save()
                await self._broadcast_code_event(normalized_email, "revoked")
                raise BadRequestException(
                    "Código anulado por demasiados intentos incorrectos. Solicitá uno nuevo."
                )
            await pending.save()
            raise BadRequestException("El código ingresado es incorrecto.")

        collection = RequesterAccessCode.get_pymongo_collection()
        updated = await collection.find_one_and_update(
            {"_id": pending.id, "estado": "pendiente"},
            {"$set": {"estado": "usado", "usado_en": now}},
        )
        if not updated:
            raise BadRequestException("Este código ya fue utilizado o revocado.")

        await self._broadcast_code_event(normalized_email, "used")
        return normalized_email

    async def list_codes(self, q: Optional[str] = None) -> List[AccessCodeItemResponse]:
        now = datetime.now(timezone.utc)
        await self._expire_stale_pending(now)

        cutoff = now - timedelta(hours=12)
        query: Dict[str, Any] = {
            "$or": [
                {"estado": "pendiente"},
                {"creado_en": {"$gte": cutoff}},
            ]
        }
        if q and q.strip():
            safe_q = re.escape(q.strip())
            query = {
                "$and": [
                    query,
                    {"correo": {"$regex": safe_q, "$options": "i"}},
                ]
            }

        docs = await RequesterAccessCode.find(query).sort("-creado_en").limit(50).to_list()
        # Mostrar pendientes primero manteniendo orden recency dentro de cada grupo
        docs.sort(key=lambda d: (0 if d.estado == "pendiente" else 1))
        return [AccessCodeItemResponse.model_validate(d) for d in docs]

    async def revoke_code(self, code_id: str) -> None:
        try:
            obj_id = PydanticObjectId(code_id)
        except Exception:
            raise BadRequestException("ID de código inválido.")

        doc = await RequesterAccessCode.get(obj_id)
        if not doc:
            raise NotFoundException("Código de acceso no encontrado.")

        if doc.estado == "pendiente":
            doc.estado = "revocado"
            await doc.save()
            await self._broadcast_code_event(str(doc.correo), "revoked")

    async def get_authorized_tickets(self, ctx: RequesterContext) -> List[RequesterTicketResponse]:
        query = _build_requester_ticket_filter(ctx)
        if not query:
            return []

        docs = (
            await Ticket.find(query)
            .sort("-fecha_creacion")
            .limit(MAX_REQUESTER_TICKETS)
            .to_list()
        )
        return [RequesterTicketResponse.model_validate(doc) for doc in docs]

    async def is_file_authorized_for_requester(
        self,
        file_id: str,
        ctx: RequesterContext,
    ) -> bool:
        ownership_query = _build_requester_ticket_filter(ctx)
        if not ownership_query or not file_id:
            return False

        safe_file_id = re.escape(file_id.strip())
        query: Dict[str, Any] = {
            "$and": [
                ownership_query,
                {"imagenes": {"$regex": safe_file_id}},
            ]
        }
        ticket = await Ticket.find_one(query)
        return ticket is not None
