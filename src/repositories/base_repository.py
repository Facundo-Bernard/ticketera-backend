from typing import TypeVar, Generic, Type, List, Optional
from beanie import Document, PydanticObjectId
from pydantic import BaseModel
from datetime import datetime, timezone

ModelType = TypeVar("ModelType", bound=Document)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    async def get(self, id: PydanticObjectId) -> Optional[ModelType]:
        return await self.model.get(id)

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        return await self.model.find_all().skip(skip).limit(limit).to_list()

    async def create(self, obj_in: CreateSchemaType) -> ModelType:
        obj = self.model(**obj_in.model_dump())
        return await obj.insert()

    async def count(self) -> int:
        return await self.model.count()

    async def update(self, id: PydanticObjectId, obj_in: UpdateSchemaType) -> Optional[ModelType]:
        db_obj = await self.get(id)
        if not db_obj:
            return None
        
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
            
        if hasattr(db_obj, "fecha_edicion"):
            db_obj.fecha_edicion = datetime.now(timezone.utc)
        elif hasattr(db_obj, "updated_at"):
            db_obj.updated_at = datetime.now(timezone.utc)
            
        await db_obj.save()
        return db_obj

    async def delete(self, id: PydanticObjectId) -> bool:
        db_obj = await self.get(id)
        if not db_obj:
            return False
        await db_obj.delete()
        return True
