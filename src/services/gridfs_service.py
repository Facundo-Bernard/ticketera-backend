import os
import mimetypes
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from bson import ObjectId
from fastapi import UploadFile
from typing import Optional, Tuple, List
from ..config.settings import settings
from ..core.exceptions import NotFoundException, BadRequestException

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/avif",
    "image/bmp",
    "image/svg+xml"
}

ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp", ".svg"
}

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

    def _validate_image(self, file: UploadFile) -> str:
        filename = file.filename or "image.png"
        content_type = (file.content_type or "").lower()
        ext = os.path.splitext(filename.lower())[1]

        # Validar si es imagen por content_type o por extensión
        is_valid_type = content_type in ALLOWED_IMAGE_TYPES or content_type.startswith("image/")
        is_valid_ext = ext in ALLOWED_IMAGE_EXTENSIONS

        if not (is_valid_type or is_valid_ext):
            raise BadRequestException(
                f"El archivo '{filename}' no es una imagen válida. Solo se permiten imágenes (PNG, JPEG, WebP, GIF, SVG, etc.)."
            )

        # Si el content_type es genérico u omitido, deducirlo por la extensión
        if not content_type or content_type == "application/octet-stream":
            guessed_type, _ = mimetypes.guess_type(filename)
            if guessed_type and guessed_type.startswith("image/"):
                content_type = guessed_type
            else:
                content_type = "image/png"

        return content_type

    async def upload_file(self, file: UploadFile) -> str:
        content_type = self._validate_image(file)
        bucket = self._get_bucket()
        grid_in = bucket.open_upload_stream(
            filename=file.filename or "image.png",
            metadata={"content_type": content_type}
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
