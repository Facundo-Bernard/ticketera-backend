from typing import List, Optional
from beanie import PydanticObjectId
from pydantic import BaseModel
from ...repositories.base_repository import BaseRepository
from .model import Candidato
from .schemas import CandidatoCreate

class CandidatoRepository(BaseRepository[Candidato, CandidatoCreate, BaseModel]):
    """
    Repositorio de persistencia para la entidad Candidato.
    Hereda operaciones CRUD estándar de BaseRepository.
    """
    def __init__(self):
        super().__init__(model=Candidato)

    async def get_by_dni(self, dni: str) -> Optional[Candidato]:
        """Busca un candidato por número de DNI."""
        return await self.model.find_one(self.model.dni == dni)

    async def get_all_sorted(self, skip: int = 0, limit: int = 100) -> List[Candidato]:
        """Obtiene candidatos ordenados por fecha de creación descendente."""
        return await self.model.find_all().sort("-fechaCreacion").skip(skip).limit(limit).to_list()
