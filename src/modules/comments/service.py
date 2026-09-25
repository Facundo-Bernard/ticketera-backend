from typing import List, Optional, Dict, Any
from fastapi import Depends
from beanie import PydanticObjectId
from ...core.exceptions import NotFoundException
from ...core.sse_manager import sse_manager
from ...models.ticket_model import Ticket
from .schemas import CommentCreate, CommentResponse
from .repository import CommentRepository

class CommentService:
    def __init__(self, repository: CommentRepository = Depends()):
        self.repository = repository

    async def get_comments_by_ticket(
        self,
        ticket_id: PydanticObjectId,
        filters: Optional[Dict[str, Any]] = None,
        skip: int = 0,
        limit: int = 10
    ) -> List[CommentResponse]:
        """
        Obtiene los comentarios paginados (por defecto de 10 en 10) aplicando el diccionario de filtros.
        """
        ticket = await Ticket.get(ticket_id)
        if not ticket:
            raise NotFoundException(f"Ticket con id {ticket_id} no encontrado")

        items = await self.repository.get_comments(
            ticket_id=ticket_id,
            filters=filters,
            skip=skip,
            limit=limit
        )

        return [
            CommentResponse(
                id=item.id,
                ticket_id=ticket_id,
                autor=item.autor,
                mensaje=item.mensaje,
                fecha_creacion=item.fecha_creacion
            )
            for item in items
        ]

    async def get_comments_count(
        self,
        ticket_id: PydanticObjectId,
        filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Obtiene el conteo total o filtrado de comentarios.
        """
        return await self.repository.count_comments(ticket_id=ticket_id, filters=filters)

    async def add_comment(
        self,
        ticket_id: PydanticObjectId,
        comment_in: CommentCreate
    ) -> CommentResponse:
        """
        Agrega un nuevo comentario al bucket del ticket y emite un evento SSE 'nuevo_comentario'.
        """
        ticket = await Ticket.get(ticket_id)
        if not ticket:
            raise NotFoundException(f"Ticket con id {ticket_id} no encontrado")

        saved_item = await self.repository.add_comment(ticket_id, comment_in)

        # Emitir evento SSE
        await sse_manager.broadcast("nuevo_comentario", {
            "ticket_id": str(ticket_id),
            "comentario": {
                "id": saved_item.id,
                "ticket_id": str(ticket_id),
                "autor": saved_item.autor,
                "mensaje": saved_item.mensaje,
                "fecha_creacion": saved_item.fecha_creacion.isoformat()
            }
        })
        try:
            from ..notifications import NotificationService
            autor_nombre = comment_in.autor_nombre or "Operador"
            preview = comment_in.contenido[:80] + ("..." if len(comment_in.contenido) > 80 else "")
            await NotificationService.broadcast({
                "title": "💬 Nuevo comentario en Ticket",
                "body": f"{autor_nombre}: {preview}",
                "url": "/"
            })
        except Exception:
            pass

        return CommentResponse(
            id=saved_item.id,
            ticket_id=ticket_id,
            autor=saved_item.autor,
            mensaje=saved_item.mensaje,
            fecha_creacion=saved_item.fecha_creacion
        )

    async def delete_comment(
        self,
        ticket_id: PydanticObjectId,
        comment_id: str
    ) -> bool:
        """
        Elimina un comentario del bucket del ticket y emite un evento SSE 'comentario_eliminado'.
        """
        ticket = await Ticket.get(ticket_id)
        if not ticket:
            raise NotFoundException(f"Ticket con id {ticket_id} no encontrado")

        deleted = await self.repository.delete_comment(ticket_id, comment_id)
        if not deleted:
            raise NotFoundException(f"Comentario con id '{comment_id}' no encontrado en el ticket {ticket_id}")

        await sse_manager.broadcast("comentario_eliminado", {
            "ticket_id": str(ticket_id),
            "comment_id": comment_id
        })
        return True
