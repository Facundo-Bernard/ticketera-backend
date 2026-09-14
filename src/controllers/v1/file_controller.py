from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse
from ...services.gridfs_service import GridFSService

router = APIRouter(prefix="/files", tags=["Files / GridFS"])

@router.head("/{file_id}", summary="Consultar metadatos de un archivo desde GridFS")
async def head_file(
    file_id: str,
    gridfs_service: GridFSService = Depends()
):
    grid_out, content_type, filename = await gridfs_service.get_file_stream(file_id)
    headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
        "Content-Type": content_type,
        "Content-Length": str(grid_out.length),
        "Cache-Control": "public, max-age=86400, immutable",
    }
    return Response(content=b"", media_type=content_type, headers=headers)

@router.get("/{file_id}", summary="Descargar / Ver un archivo desde GridFS")
async def get_file(
    file_id: str,
    gridfs_service: GridFSService = Depends()
):
    grid_out, content_type, filename = await gridfs_service.get_file_stream(file_id)
    
    async def file_iterator():
        while chunk := await grid_out.readchunk():
            yield chunk

    return StreamingResponse(
        file_iterator(),
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "public, max-age=86400, immutable"
        }
    )
