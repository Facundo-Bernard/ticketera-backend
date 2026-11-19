from typing import Optional
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from ...core.exceptions import UnauthorizedException
from ...services.gridfs_service import GridFSService
from ...modules.auth import get_optional_current_user, User
from ...modules.requester.security import extract_requester_context
from ...modules.requester.service import RequesterService

router = APIRouter(prefix="/files", tags=["Files / GridFS"])


async def _ensure_file_access(
    request: Request,
    file_id: str,
    current_user: Optional[User],
    requester_service: RequesterService,
) -> None:
    if current_user is not None:
        return

    ctx = extract_requester_context(request)
    if not ctx.has_any_access:
        raise UnauthorizedException("Se requiere sesión o token de autenticación")

    authorized = await requester_service.is_file_authorized_for_requester(file_id, ctx)
    if not authorized:
        raise UnauthorizedException("No tenés permisos para acceder a este archivo")


@router.head("/{file_id}", summary="Consultar metadatos de un archivo desde GridFS (Operador / Admin / Solicitante autorizado)")
async def head_file(
    file_id: str,
    request: Request,
    gridfs_service: GridFSService = Depends(),
    requester_service: RequesterService = Depends(),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    await _ensure_file_access(request, file_id, current_user, requester_service)
    grid_out, content_type, filename = await gridfs_service.get_file_stream(file_id)
    safe_filename = filename.replace('"', '').replace('\r', '').replace('\n', '') if filename else "archivo"
    headers = {
        "Content-Disposition": f'inline; filename="{safe_filename}"',
        "Content-Type": content_type,
        "Content-Length": str(grid_out.length),
        "Cache-Control": "private, max-age=86400, immutable",
    }
    return Response(content=b"", media_type=content_type, headers=headers)


@router.get("/{file_id}", summary="Descargar / Ver un archivo desde GridFS (Operador / Admin / Solicitante autorizado)")
async def get_file(
    file_id: str,
    request: Request,
    gridfs_service: GridFSService = Depends(),
    requester_service: RequesterService = Depends(),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    await _ensure_file_access(request, file_id, current_user, requester_service)
    grid_out, content_type, filename = await gridfs_service.get_file_stream(file_id)
    safe_filename = filename.replace('"', '').replace('\r', '').replace('\n', '') if filename else "archivo"
    
    async def file_iterator():
        while chunk := await grid_out.readchunk():
            yield chunk

    return StreamingResponse(
        file_iterator(),
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{safe_filename}"',
            "Cache-Control": "private, max-age=86400, immutable"
        }
    )
