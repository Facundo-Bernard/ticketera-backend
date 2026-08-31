from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from ...services.gridfs_service import GridFSService

router = APIRouter(prefix="/files", tags=["Files / GridFS"])

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
        headers={"Content-Disposition": f'inline; filename="{filename}"'}
    )
