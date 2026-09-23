from typing import List, Optional, Tuple
from fastapi import Depends, UploadFile
from beanie import PydanticObjectId
from ...core.exceptions import NotFoundException
from .model import Candidato, ProductoSeleccionado
from .schemas import CandidatoCreate
from .repository import CandidatoRepository
from .gridfs_service import CandidatoGridFSService

class CandidatoService:
    """
    Servicio de lógica de negocio para la gestión de candidatos y su papelería.
    """
    def __init__(
        self,
        repository: CandidatoRepository = Depends(),
        gridfs_service: CandidatoGridFSService = Depends()
    ):
        self.repository = repository
        self.gridfs_service = gridfs_service

    async def register_candidato(
        self,
        candidato_in: CandidatoCreate,
        papeleria_file: Optional[UploadFile] = None
    ) -> Candidato:
        """
        Registra un nuevo candidato y, si se provee, almacena su archivo de papelería en GridFS
        bajo el bucket aislado 'candidatos_papeleria' con su propio identificador único de archivo.
        """
        papeleria_file_ids = []
        papeleria_url = None

        if papeleria_file is not None and papeleria_file.filename:
            file_id = await self.gridfs_service.upload_papeleria(papeleria_file)
            papeleria_file_ids.append(file_id)
            papeleria_url = f"/api/v1/candidatos/papeleria/{file_id}"

        data = candidato_in.model_dump()
        prod_data = data.pop("productoSeleccionado")
        producto = ProductoSeleccionado(**prod_data)
        data.pop("papeleria", None)

        candidato = Candidato(
            **data,
            productoSeleccionado=producto,
            papeleria=papeleria_url,
            papeleria_file_ids=papeleria_file_ids
        )
        await candidato.insert()
        return candidato

    async def get_candidato(self, id: PydanticObjectId) -> Candidato:
        """
        Obtiene un candidato por su ID o lanza NotFoundException si no existe.
        """
        candidato = await self.repository.get(id)
        if not candidato:
            raise NotFoundException(f"Candidato con id '{id}' no encontrado")
        return candidato

    async def list_candidatos(self, skip: int = 0, limit: int = 100) -> List[Candidato]:
        """
        Retorna la lista de candidatos ordenados por fecha de creación más reciente.
        """
        return await self.repository.get_all_sorted(skip=skip, limit=limit)

    async def get_papeleria_stream(self, file_id: str) -> Tuple:
        """
        Retorna el stream binario de GridFS para el archivo de papelería identificado por su file_id.
        """
        return await self.gridfs_service.get_papeleria_stream(file_id)

    async def delete_candidato(self, id: PydanticObjectId) -> bool:
        """
        Elimina un candidato y purga en cascada todos sus archivos de papelería asociados en GridFS.
        """
        candidato = await self.repository.get(id)
        if not candidato:
            raise NotFoundException(f"Candidato con id '{id}' no encontrado")

        # Purga física en cascada de todos los archivos asociados en GridFS
        for fid in candidato.papeleria_file_ids:
            await self.gridfs_service.delete_papeleria(fid)

        await candidato.delete()
        return True
