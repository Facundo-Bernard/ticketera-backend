from beanie import init_beanie, Document
from typing import List, Type
from .settings import settings
import logging
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

async def init_db(models: List[Type[Document]] = None):
    if models is None:
        models = []
        
    try:
        client = AsyncIOMotorClient(settings.MONGO_URI)
        await init_beanie(
            database=client[settings.MONGO_DB_NAME],
            document_models=models,
            allow_index_dropping=True
        )
        logger.info("Successfully connected to MongoDB and initialized Beanie")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise e
