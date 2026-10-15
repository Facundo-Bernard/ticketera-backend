from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, Query, status
from beanie import PydanticObjectId
from .schemas import CommentCreate, CommentResponse
from .service import CommentService
from ..auth import get_current_user, get_current_admin, User

router = APIRouter(prefix="/tickets/{ticket_id}/comments", tags=["Comentarios"])

@router.get(
    "",
    response_model=List[CommentResponse],
    summary="Listar comentarios de un ticket (Bucket Pattern con $slice y Filtros)"
)
async def get_comments(
    ticket_id: PydanticObjectId,
    autor: Optional[str] = Query(None, description="Filtrar comentarios por nombre o correo de autor"),
    fecha_desde: Optional[str] = Query(None, description="Filtrar por fecha desde (YYYY-MM-DD o ISO)"),
    fecha_hasta: Optional[str] = Query(None, description="Filtrar por fecha hasta (YYYY-MM-DD o ISO)"),
    skip: int = Query(0, ge=0, description="Cantidad de comentarios a omitir"),
    limit: int = Query(10, ge=1, le=100, description="Cantidad de comentarios por lote (por defecto 10)"),
    service: CommentService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene los comentarios de un ticket utilizando el patrón Bucket con proyección $slice de MongoDB.
    Trae los comentarios por lotes (ej. de 10 en 10) y permite filtrar por autor o rango de fechas.
    """
    filter_dict = {}
    if autor:
        filter_dict["autor"] = autor
    if fecha_desde:
        filter_dict["fecha_desde"] = fecha_desde
    if fecha_hasta:
        filter_dict["fecha_hasta"] = fecha_hasta

    return await service.get_comments_by_ticket(
        ticket_id=ticket_id,
        filters=filter_dict,
        skip=skip,
        limit=limit
    )

@router.get(
    "/count",
    summary="Contar comentarios de un ticket (con filtros opcionales)"
)
async def get_comments_count(
    ticket_id: PydanticObjectId,
    autor: Optional[str] = Query(None, description="Filtrar conteo por autor"),
    fecha_desde: Optional[str] = Query(None, description="Filtrar conteo por fecha desde"),
    fecha_hasta: Optional[str] = Query(None, description="Filtrar conteo por fecha hasta"),
    service: CommentService = Depends(),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Retorna la cantidad de comentarios en el bucket. Sin filtros se resuelve en O(1) leyendo el campo 'total'.
    """
    filter_dict = {}
    if autor:
        filter_dict["autor"] = autor
    if fecha_desde:
        filter_dict["fecha_desde"] = fecha_desde
    if fecha_hasta:
        filter_dict["fecha_hasta"] = fecha_hasta

    count = await service.get_comments_count(ticket_id, filters=filter_dict)
    return {"ticket_id": str(ticket_id), "total": count}

@router.post(
    "",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un comentario en el bucket del ticket"
)
async def create_comment(
    ticket_id: PydanticObjectId,
    comment_in: CommentCreate,
    service: CommentService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Inserta un nuevo comentario en el bucket del ticket mediante $push atómico y emite evento SSE 'nuevo_comentario'.
    """
    return await service.add_comment(ticket_id, comment_in)

@router.delete(
    "/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un comentario del bucket (Admin)"
)
async def delete_comment(
    ticket_id: PydanticObjectId,
    comment_id: str,
    service: CommentService = Depends(),
    current_user: User = Depends(get_current_admin)
):
    """
    Elimina un comentario del bucket mediante $pull atómico y emite evento SSE 'comentario_eliminado'.
    """
    await service.delete_comment(ticket_id, comment_id)
