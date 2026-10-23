from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse
from ...services.gridfs_service import GridFSService
from ...modules.auth import get_current_user, User

router = APIRouter(prefix="/files", tags=["Files / GridFS"])

@router.head("/{file_id}", summary="Consultar metadatos de un archivo desde GridFS (Operador / Admin)")
async def head_file(
    file_id: str,
    gridfs_service: GridFSService = Depends(),
    current_user: User = Depends(get_current_user)
):
    grid_out, content_type, filename = await gridfs_service.get_file_stream(file_id)
    safe_filename = filename.replace('"', '').replace('\r', '').replace('\n', '') if filename else "archivo"
    headers = {
        "Content-Disposition": f'inline; filename="{safe_filename}"',
        "Content-Type": content_type,
        "Content-Length": str(grid_out.length),
        "Cache-Control": "private, max-age=86400, immutable",
    }
    return Response(content=b"", media_type=content_type, headers=headers)

@router.get("/{file_id}", summary="Descargar / Ver un archivo desde GridFS (Operador / Admin)")
async def get_file(
    file_id: str,
    gridfs_service: GridFSService = Depends(),
    current_user: User = Depends(get_current_user)
):
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
