import os
import mimetypes
from typing import Optional, Tuple
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from fastapi import UploadFile
from ...config.settings import settings
from ...core.exceptions import NotFoundException, BadRequestException

ALLOWED_PAPELERIA_TYPES = {
    # Documentos permitidos: únicamente PDF
    "application/pdf",
    # Imágenes permitidas
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/bmp"
}

ALLOWED_PAPELERIA_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".webp", ".bmp"
}

MIME_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".bmp": "image/bmp"
}

# Límite máximo de peso: 25 MB
MAX_PAPELERIA_SIZE_BYTES = 25 * 1024 * 1024

class CandidatoGridFSService:
    """
    Servicio de almacenamiento en MongoDB GridFS exclusivo para la papelería de candidatos.
    Utiliza el bucket aislado 'candidatos_papeleria' para evitar mezclar datos con la ticketera.
    """
    BUCKET_NAME = "candidatos_papeleria"

    def __init__(self):
        self._bucket: Optional[AsyncIOMotorGridFSBucket] = None
        self._client: Optional[AsyncIOMotorClient] = None

    def _get_bucket(self) -> AsyncIOMotorGridFSBucket:
        if self._bucket is None:
            self._client = AsyncIOMotorClient(settings.MONGO_URI)
            db = self._client[settings.MONGO_DB_NAME]
            self._bucket = AsyncIOMotorGridFSBucket(db, bucket_name=self.BUCKET_NAME)
        return self._bucket

    def validate_file(self, file: UploadFile) -> str:
        """
        Valida que el archivo subido sea estrictamente PDF o imagen y no supere el peso máximo.
        """
        filename = file.filename or "archivo"
        content_type = (file.content_type or "").lower()
        ext = os.path.splitext(filename.lower())[1]

        is_valid_type = content_type in ALLOWED_PAPELERIA_TYPES or content_type.startswith("image/")
        is_valid_ext = ext in ALLOWED_PAPELERIA_EXTENSIONS

        if not (is_valid_type or is_valid_ext):
            raise BadRequestException(
                f"El archivo '{filename}' no tiene un formato permitido para papelería. "
                f"Solo se admiten documentos PDF o imágenes (PNG, JPEG, WebP, BMP)."
            )

        # Normalizar content_type si fue omitido o enviado genérico
        if not content_type or content_type in ("application/octet-stream", "binary/octet-stream"):
            if ext in MIME_BY_EXTENSION:
                content_type = MIME_BY_EXTENSION[ext]
            else:
                guessed_type, _ = mimetypes.guess_type(filename)
                content_type = guessed_type or "application/pdf"

        return content_type

    async def upload_papeleria(self, file: UploadFile) -> str:
        """
        Sube un único archivo de papelería al bucket 'candidatos_papeleria' de GridFS.
        Retorna el ObjectId generado en formato string.
        """
        content_type = self.validate_file(file)

        content = await file.read()
        if len(content) > MAX_PAPELERIA_SIZE_BYTES:
            raise BadRequestException(
                f"El archivo de papelería '{file.filename}' supera el tamaño máximo permitido de 25 MB."
            )

        bucket = self._get_bucket()
        grid_in = bucket.open_upload_stream(
            filename=file.filename or "papeleria.pdf",
            metadata={"content_type": content_type}
        )
        await grid_in.write(content)
        await grid_in.close()
        return str(grid_in._id)

    async def get_papeleria_stream(self, file_id: str) -> Tuple:
        """
        Abre un stream de lectura para descargar o previsualizar el archivo desde GridFS.
        Retorna (grid_out, content_type, filename).
        """
        try:
            oid = ObjectId(file_id)
        except Exception:
            raise NotFoundException("ID de archivo de papelería inválido")

        try:
            bucket = self._get_bucket()
            grid_out = await bucket.open_download_stream(oid)
            content_type = "application/pdf"
            if grid_out.metadata and "content_type" in grid_out.metadata:
                content_type = grid_out.metadata["content_type"]
            return grid_out, content_type, grid_out.filename
        except Exception:
            raise NotFoundException("Archivo de papelería no encontrado en GridFS")

    async def delete_papeleria(self, file_id: str):
        """
        Elimina físicamente el archivo y sus chunks del bucket 'candidatos_papeleria' de GridFS.
        """
        try:
            oid = ObjectId(file_id)
            bucket = self._get_bucket()
            await bucket.delete(oid)
        except Exception:
            # Silenciar si ya fue borrado para asegurar idempotencia en cascada
            pass
