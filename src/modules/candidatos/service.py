from typing import List
from fastapi import Depends
from beanie import PydanticObjectId
from ...core.exceptions import NotFoundException
from .model import Candidato, ProductoSeleccionado
from .schemas import CandidatoCreate
from .repository import CandidatoRepository

class CandidatoService:
    """
    Servicio de lógica de negocio para la gestión de candidatos.
    """
    def __init__(self, repository: CandidatoRepository = Depends()):
        self.repository = repository

    async def register_candidato(self, candidato_in: CandidatoCreate) -> Candidato:
        """
        Registra un nuevo candidato en la base de datos a partir del payload validado.
        """
        data = candidato_in.model_dump()
        prod_data = data.pop("productoSeleccionado")
        producto = ProductoSeleccionado(**prod_data)
        candidato = Candidato(**data, productoSeleccionado=producto)
        return await candidato.insert()

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

    async def delete_candidato(self, id: PydanticObjectId) -> bool:
        """
        Elimina un candidato por su ID o lanza NotFoundException si no existe.
        """
        deleted = await self.repository.delete(id)
        if not deleted:
            raise NotFoundException(f"Candidato con id '{id}' no encontrado")
        return True

