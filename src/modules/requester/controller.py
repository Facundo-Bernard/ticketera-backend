import asyncio
import json
from typing import List, Optional, Set
from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from ...core.sse_manager import sse_manager
from ..auth import User, get_current_user
from .schemas import (
    AccessCodeItemResponse,
    OperatorGenerateCodeInput,
    RequesterRequestCodeInput,
    RequesterRequestCodeResponse,
    RequesterTicketsSessionResponse,
    RequesterVerifyCodeInput,
)
from .security import (
    clear_requester_session_cookie,
    extract_requester_context,
    set_requester_session_cookie,
)
from .service import RequesterService, sanitize_ticket_for_requester

router = APIRouter(prefix="/requester", tags=["Requester Portal"])


@router.get(
    "/tickets",
    response_model=RequesterTicketsSessionResponse,
    summary="Listar tickets autorizados del solicitante (sesión o equipo actual)",
)
async def list_requester_tickets(
    request: Request,
    service: RequesterService = Depends(),
):
    ctx = extract_requester_context(request)
    items = await service.get_authorized_tickets(ctx)
    return RequesterTicketsSessionResponse(
        linked_email=ctx.email,
        local_tickets_count=len(ctx.local_ticket_ids),
        items=items,
    )


@router.post(
    "/request-code",
    response_model=RequesterRequestCodeResponse,
    summary="Solicitar un código temporal de 15 min para recuperar el historial completo",
)
async def request_access_code(
    payload: RequesterRequestCodeInput,
    service: RequesterService = Depends(),
):
    return await service.request_code(str(payload.correo))


@router.post(
    "/verify-code",
    response_model=RequesterTicketsSessionResponse,
    summary="Validar código temporal y vincular el navegador al historial del correo",
)
async def verify_access_code(
    payload: RequesterVerifyCodeInput,
    request: Request,
    response: Response,
    service: RequesterService = Depends(),
):
    verified_email = await service.verify_code(str(payload.correo), payload.codigo)
    set_requester_session_cookie(response, verified_email, request)

    ctx = extract_requester_context(request)
    ctx.email = verified_email
    items = await service.get_authorized_tickets(ctx)
    return RequesterTicketsSessionResponse(
        linked_email=verified_email,
        local_tickets_count=len(ctx.local_ticket_ids),
        items=items,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Desvincular la sesión de historial completo de este navegador",
)
async def requester_logout(request: Request, response: Response):
    clear_requester_session_cookie(response, request)
    return {"status": "ok"}


@router.get(
    "/stream",
    summary="Canal SSE filtrado para actualizaciones en vivo de los tickets del solicitante",
)
async def requester_ticket_stream(request: Request):
    ctx = extract_requester_context(request)
    authorized_email = ctx.email.lower() if ctx.email else None
    authorized_ids: Set[str] = set() if authorized_email else {str(tid) for tid in ctx.local_ticket_ids}

    last_event_id: Optional[int] = None
    raw_last_id = request.headers.get("last-event-id")
    if raw_last_id:
        try:
            last_event_id = int(raw_last_id.strip())
        except ValueError:
            last_event_id = None

    async def event_generator():
        queue = await sse_manager.subscribe(last_event_id=last_event_id)
        try:
            yield ": connected\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=15.0)
                    event = item.get("event", "")
                    raw_data = item.get("data") or {}
                    event_id = item.get("id")
                    id_line = f"id: {event_id}\n" if event_id is not None else ""

                    if event in ("nuevo_ticket", "ticket_actualizado"):
                        ticket_id = str(raw_data.get("id", ""))
                        ticket_correo = str(raw_data.get("correo", "")).strip().lower()
                        is_owner = (
                            ticket_correo == authorized_email
                            if authorized_email
                            else bool(ticket_id and ticket_id in authorized_ids)
                        )
                        if not is_owner:
                            continue
                        if not authorized_email and ticket_id:
                            authorized_ids.add(ticket_id)
                        sanitized = sanitize_ticket_for_requester(raw_data)
                        yield f"{id_line}event: {event}\ndata: {json.dumps(sanitized)}\n\n"

                    elif event == "ticket_eliminado":
                        ticket_id = str(raw_data.get("id") or raw_data.get("ticket_id") or "")
                        ticket_correo = str(raw_data.get("correo", "")).strip().lower()
                        is_owner = (
                            ticket_correo == authorized_email
                            if authorized_email
                            else bool(ticket_id and ticket_id in authorized_ids)
                        )
                        if not is_owner or not ticket_id:
                            continue
                        yield f"{id_line}event: ticket_eliminado\ndata: {json.dumps({'id': ticket_id})}\n\n"

                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            sse_manager.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/codes",
    response_model=List[AccessCodeItemResponse],
    summary="Listar códigos temporales pendientes y recientes (Operador / Admin)",
)
async def list_access_codes(
    q: Optional[str] = Query(None, description="Filtrar por correo"),
    service: RequesterService = Depends(),
    current_user: User = Depends(get_current_user),
):
    return await service.list_codes(q=q)


@router.post(
    "/codes",
    response_model=AccessCodeItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generar un código temporal de 15 min para un correo (Operador / Admin)",
)
async def generate_access_code(
    payload: OperatorGenerateCodeInput,
    service: RequesterService = Depends(),
    current_user: User = Depends(get_current_user),
):
    return await service.generate_code_for_operator(
        correo=str(payload.correo),
        operator_email=str(current_user.email),
    )


@router.delete(
    "/codes/{code_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revocar un código temporal pendiente (Operador / Admin)",
)
async def revoke_access_code(
    code_id: str,
    service: RequesterService = Depends(),
    current_user: User = Depends(get_current_user),
):
    await service.revoke_code(code_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
