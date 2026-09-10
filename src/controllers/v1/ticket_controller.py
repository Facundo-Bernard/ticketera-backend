import asyncio
import json
from fastapi import APIRouter, Depends, status, UploadFile, File, Form, Query, Request, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Optional, Union
from datetime import datetime, timezone
from pydantic import EmailStr, BaseModel, Field
from beanie import PydanticObjectId
from ...schemas.ticket_schema import TicketCreate, TicketUpdate, TicketResponse
from ...models.ticket_model import PrioridadEnum, EstadoEnum, Frecuencia
from ...services.ticket_service import TicketService
from ...services.gridfs_service import GridFSService
from ...core.exceptions import BadRequestException
from ...core.sse_manager import sse_manager
from ...core.ticket_lock_manager import ticket_lock_manager

class LockRequest(BaseModel):
    usuario: str = Field(..., min_length=1, description="Nombre o correo del operador que solicita el bloqueo")

class UnlockRequest(BaseModel):
    usuario: Optional[str] = Field(None, description="Nombre o correo del operador que libera el bloqueo (opcional)")

router = APIRouter(prefix="/tickets", tags=["Tickets"])

@router.post("/", response_model=TicketResponse, status_code=status.HTTP_201_CREATED, summary="Crear un ticket con texto e imágenes opcionales (Con Rollback)")
async def create_ticket(
    titulo: str = Form(..., min_length=3, max_length=150, description="Título del problema"),
    descripcion: str = Form(..., description="Descripción detallada"),
    correo: EmailStr = Form(..., description="Correo del solicitante"),
    prioridad: PrioridadEnum = Form(PrioridadEnum.MEDIA, description="Prioridad del ticket"),
    asignar: Optional[str] = Form(None, description="Técnico asignado (opcional)"),
    columna: Optional[int] = Form(1, description="Columna del ticket (1: Ticket, 2: Hitos, 3: Tareas, 4: Tareas periódicas)"),
    frecuencia: Optional[str] = Form(None, description="Frecuencia periódica en formato JSON: {\"numero\": 1, \"periodo\": \"Semanas\"}"),
    files: List[UploadFile] = File(default=[], description="Solo archivos de imagen permitidos (PNG, JPEG, WebP, GIF, SVG)"),
    service: TicketService = Depends(),
    gridfs_service: GridFSService = Depends()
):
    frecuencia_obj: Optional[Frecuencia] = None
    if frecuencia:
        try:
            if isinstance(frecuencia, str):
                frecuencia_data = json.loads(frecuencia)
            else:
                frecuencia_data = frecuencia
            frecuencia_obj = Frecuencia.model_validate(frecuencia_data)
        except Exception as e:
            raise BadRequestException(f"Formato de frecuencia inválido: {e}")

    ticket_in = TicketCreate(
        titulo=titulo,
        descripcion=descripcion,
        correo=correo,
        prioridad=prioridad,
        asignar=asignar,
        columna=columna or 1,
        frecuencia=frecuencia_obj
    )
    # Filtrar solo archivos válidos con nombre
    valid_files = [f for f in files if getattr(f, "filename", None)]

    return await service.create_ticket_with_rollback(
        ticket_in=ticket_in,
        files=valid_files if valid_files else None,
        gridfs_service=gridfs_service
    )

@router.get("/stream", summary="Canal en tiempo real (Server-Sent Events) para nuevos tickets")
async def ticket_stream(request: Request):
    """
    Canal continuo SSE para notificaciones en vivo.
    Emite eventos 'nuevo_ticket' y comentarios keep-alive ': ping' cada 15 segundos.
    """
    async def event_generator():
        queue = await sse_manager.subscribe()
        try:
            # Emitir inmediatamente al cliente recien conectado todos los bloqueos activos
            active_locks = ticket_lock_manager.get_active_locks()
            for t_id, lock in active_locks.items():
                expira_segundos = max(0, int((lock.expira_en - datetime.now(timezone.utc)).total_seconds()))
                payload = {
                    "ticket_id": str(t_id),
                    "usuario": lock.usuario,
                    "expira_en_segundos": expira_segundos
                }
                yield f"event: ticket_bloqueado\ndata: {json.dumps(payload)}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    # Esperar evento con timeout de 15 segundos para keep-alive ping
                    item = await asyncio.wait_for(queue.get(), timeout=15.0)
                    event = item.get("event", "nuevo_ticket")
                    data_str = json.dumps(item.get("data", {}))
                    yield f"event: {event}\ndata: {data_str}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive ping para evitar que Railway o proxies cierren la conexión
                    yield ": ping\n\n"
        finally:
            sse_manager.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.get("/", response_model=List[TicketResponse], summary="Listar tickets con filtros y paginación")
async def get_tickets(
    fecha_desde: Optional[str] = Query(None, description="Fecha de inicio flexible (ej: 2026-08-01 o 2026-08-01T14:30:00)"),
    fecha_hasta: Optional[str] = Query(None, description="Fecha fin flexible (ej: 2026-08-31 o 2026-08-31T23:59:59)"),
    estado: Optional[EstadoEnum] = Query(None, description="Filtrar por estado del ticket"),
    prioridad: Optional[PrioridadEnum] = Query(None, description="Filtrar por prioridad"),
    asignar: Optional[str] = Query(None, description="Filtrar por técnico/usuario asignado"),
    columna: Optional[int] = Query(None, ge=1, le=4, description="Filtrar por columna (1, 2, 3, 4)"),
    leido: Optional[bool] = Query(None, description="Filtrar por leído (true/false)"),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: int = Query(100, ge=1, le=500, description="Límite de registros a devolver"),
    service: TicketService = Depends()
):
    filters = {
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "estado": estado,
        "prioridad": prioridad,
        "asignar": asignar,
        "columna": columna,
        "leido": leido
    }
    clean_filters = {k: v for k, v in filters.items() if v is not None}
    return await service.get_all_tickets(
        filters=clean_filters if clean_filters else None,
        skip=skip,
        limit=limit
    )

@router.patch("/{id}/read", response_model=TicketResponse, summary="Marcar ticket como leído")
async def mark_ticket_as_read(id: PydanticObjectId, service: TicketService = Depends()):
    return await service.mark_as_read(id)

@router.post("/{id}/bloquear", summary="Bloquear ticket para edición exclusiva (evita colisiones concurrentes)")
async def lock_ticket(
    id: PydanticObjectId,
    payload: LockRequest,
    service: TicketService = Depends()
):
    ticket = await service.get_ticket(id)
    success, lock_info = ticket_lock_manager.acquire_lock(str(id), payload.usuario)
    if not success and lock_info:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El ticket está siendo editado por {lock_info.usuario}",
            headers={"X-Locked-By": lock_info.usuario}
        )

    # Notificar a todas las pantallas vía SSE
    try:
        await sse_manager.broadcast("ticket_bloqueado", {
            "ticket_id": str(id),
            "identificador": getattr(ticket, "identificador", str(id)),
            "usuario": payload.usuario,
            "expira_en_segundos": ticket_lock_manager.ttl_seconds
        })
    except Exception:
        pass

    return {
        "status": "bloqueado",
        "ticket_id": str(id),
        "usuario": payload.usuario,
        "expira_en_segundos": ticket_lock_manager.ttl_seconds
    }

@router.post("/{id}/desbloquear", summary="Liberar bloqueo de edición de un ticket")
async def unlock_ticket(
    id: PydanticObjectId,
    payload: Optional[UnlockRequest] = None,
    service: TicketService = Depends()
):
    usuario = payload.usuario if payload else None
    ticket_lock_manager.release_lock(str(id), usuario)

    # Notificar a todas las pantallas vía SSE
    try:
        await sse_manager.broadcast("ticket_desbloqueado", {
            "ticket_id": str(id)
        })
    except Exception:
        pass

    return {"status": "desbloqueado", "ticket_id": str(id)}

@router.get("/{id}/bloqueo", summary="Consultar estado de bloqueo de un ticket")
async def get_ticket_lock_status(
    id: PydanticObjectId,
    service: TicketService = Depends()
):
    await service.get_ticket(id)
    lock = ticket_lock_manager.is_locked(str(id))
    if not lock:
        return {"bloqueado": False}
    return {
        "bloqueado": True,
        "usuario": lock.usuario,
        "expira_en": lock.expira_en.isoformat()
    }

@router.get("/{id}", response_model=TicketResponse, summary="Obtener ticket por ID")
async def get_ticket(id: PydanticObjectId, service: TicketService = Depends()):
    return await service.get_ticket(id)

@router.patch("/{id}", response_model=TicketResponse, summary="Actualizar ticket por ID (PATCH)")
async def update_ticket(id: PydanticObjectId, ticket_in: TicketUpdate, service: TicketService = Depends()):
    return await service.update_ticket(id, ticket_in)

@router.post("/{id}/images", response_model=TicketResponse, summary="Adjuntar una o varias imágenes a un ticket mediante GridFS")
async def upload_ticket_images(
    id: PydanticObjectId,
    files: List[UploadFile] = File(..., description="Selecciona archivos de imagen permitidos (PNG, JPEG, WebP, GIF, SVG)"),
    ticket_service: TicketService = Depends(),
    gridfs_service: GridFSService = Depends()
):
    file_ids = await gridfs_service.upload_files(files)
    image_urls = [f"/api/v1/files/{fid}" for fid in file_ids]
    return await ticket_service.add_images_to_ticket(id, image_urls)

@router.delete("/{id}/images/{file_id}", response_model=TicketResponse, summary="Eliminar una imagen específica de un ticket y borrarla de GridFS")
async def delete_ticket_image(
    id: PydanticObjectId,
    file_id: str,
    ticket_service: TicketService = Depends(),
    gridfs_service: GridFSService = Depends()
):
    return await ticket_service.remove_image_from_ticket(id, file_id, gridfs_service)

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar ticket por ID y todas sus fotos asociadas")
async def delete_ticket(
    id: PydanticObjectId,
    service: TicketService = Depends(),
    gridfs_service: GridFSService = Depends()
):
    await service.delete_ticket(id, gridfs_service)
