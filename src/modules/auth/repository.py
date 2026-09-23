from typing import Optional
from beanie import PydanticObjectId
from pydantic import BaseModel
from ...repositories.base_repository import BaseRepository
from .model import User

class UserRepository(BaseRepository[User, BaseModel, BaseModel]):
    """
    Repositorio de persistencia para la entidad User.
    Hereda operaciones CRUD estándar de BaseRepository.
    """
    def __init__(self):
        super().__init__(model=User)

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Busca un usuario por su correo electrónico (case-insensitive).
        """
        return await self.model.find_one(self.model.email == email.lower().strip())
