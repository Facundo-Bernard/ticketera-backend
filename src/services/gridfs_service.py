import os
import mimetypes
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from bson import ObjectId
from fastapi import UploadFile
from typing import Optional, Tuple, List
from ..config.settings import settings
from ..core.exceptions import NotFoundException, BadRequestException

ALLOWED_FILE_TYPES = {
    # Imágenes seguras (sin SVG para prevenir Stored XSS)
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/avif",
    "image/bmp",
    # Documentos
    "application/pdf",
    "text/csv",
    "application/csv",
    "text/plain",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
}

ALLOWED_FILE_EXTENSIONS = {
    # Imágenes seguras (SVG excluido)
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp",
    # Documentos
    ".pdf", ".csv", ".xlsx", ".xls", ".txt"
}

# Aliases de compatibilidad hacia atrás
ALLOWED_IMAGE_TYPES = ALLOWED_FILE_TYPES
ALLOWED_IMAGE_EXTENSIONS = ALLOWED_FILE_EXTENSIONS

MIME_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".txt": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".avif": "image/avif",
}

# Límite máximo de peso por archivo: 25 MB
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024

class GridFSService:
    def __init__(self):
        self._bucket: Optional[AsyncIOMotorGridFSBucket] = None
        self._client: Optional[AsyncIOMotorClient] = None

    def _get_bucket(self) -> AsyncIOMotorGridFSBucket:
        if self._bucket is None:
            self._client = AsyncIOMotorClient(settings.MONGO_URI)
            db = self._client[settings.MONGO_DB_NAME]
            self._bucket = AsyncIOMotorGridFSBucket(db)
        return self._bucket

    def _validate_file(self, file: UploadFile) -> str:
        filename = file.filename or "archivo"
        content_type = (file.content_type or "").lower()
        ext = os.path.splitext(filename.lower())[1]

        # Validar coherencia estricta: tanto la extensión como el tipo MIME deben ser permitidos
        is_valid_ext = ext in ALLOWED_FILE_EXTENSIONS
        is_valid_type = content_type in ALLOWED_FILE_TYPES or (
            content_type.startswith("image/") and ext in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp"}
        )

        if not (is_valid_type and is_valid_ext):
            raise BadRequestException(
                f"El archivo '{filename}' no tiene un formato seguro o permitido. Solo se permiten imágenes estáticas (PNG, JPEG, WebP, etc.) y documentos (PDF, CSV, XLSX, TXT). Los archivos SVG o ejecutables están estrictamente prohibidos."
            )

        # Si el content_type es genérico u omitido, deducirlo por la extensión
        if not content_type or content_type in ("application/octet-stream", "binary/octet-stream"):
            if ext in MIME_BY_EXTENSION:
                content_type = MIME_BY_EXTENSION[ext]
            else:
                guessed_type, _ = mimetypes.guess_type(filename)
                content_type = guessed_type or "application/octet-stream"

        return content_type

    def _validate_image(self, file: UploadFile) -> str:
        """Alias para mantener compatibilidad hacia atrás."""
        return self._validate_file(file)

    async def upload_file(self, file: UploadFile) -> str:
        content_type = self._validate_file(file)
        
        content = await file.read()
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise BadRequestException(
                f"El archivo '{file.filename}' supera el tamaño máximo permitido de 25 MB."
            )

        bucket = self._get_bucket()
        grid_in = bucket.open_upload_stream(
            filename=file.filename or "archivo",
            metadata={"content_type": content_type}
        )
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
