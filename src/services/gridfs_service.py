from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from bson import ObjectId
from fastapi import UploadFile
from typing import Optional, Tuple, List
from ..config.settings import settings
from ..core.exceptions import NotFoundException

class GridFSService:
    def __init__(self):
        self._bucket: Optional[AsyncIOMotorGridFSBucket] = None
        self._client: Optional[AsyncIOMotorClient] = None

    def _get_bucket(self) -> AsyncIOMotorGridFSBucket:
        if self._bucket is None:
            self._client = AsyncIOMotorClient(settings.MONGO_URI)
            db = self._client.get_default_database()
            self._bucket = AsyncIOMotorGridFSBucket(db)
        return self._bucket

    async def upload_file(self, file: UploadFile) -> str:
        bucket = self._get_bucket()
        grid_in = bucket.open_upload_stream(
            filename=file.filename or "image.png",
            metadata={"content_type": file.content_type or "image/png"}
        )
        content = await file.read()
        await grid_in.write(content)
        await grid_in.close()
        return str(grid_in._id)

    async def upload_files(self, files: List[UploadFile]) -> List[str]:
        uploaded_ids = []
        for file in files:
            file_id = await self.upload_file(file)
            uploaded_ids.append(file_id)
        return uploaded_ids

    async def get_file_stream(self, file_id: str) -> Tuple:
        try:
            oid = ObjectId(file_id)
        except Exception:
            raise NotFoundException("ID de archivo inválido")
            
        try:
            bucket = self._get_bucket()
            grid_out = await bucket.open_download_stream(oid)
            content_type = "application/octet-stream"
            if grid_out.metadata and "content_type" in grid_out.metadata:
                content_type = grid_out.metadata["content_type"]
            return grid_out, content_type, grid_out.filename
        except Exception:
            raise NotFoundException("Archivo no encontrado en GridFS")

    async def delete_file(self, file_id: str):
        try:
            oid = ObjectId(file_id)
            bucket = self._get_bucket()
            await bucket.delete(oid)
        except Exception:
            raise NotFoundException("Archivo no encontrado para eliminar")
