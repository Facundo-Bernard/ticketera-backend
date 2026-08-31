from beanie import init_beanie, Document
from typing import List, Type
from .settings import settings
import logging

logger = logging.getLogger(__name__)

async def init_db(models: List[Type[Document]] = None):
    if models is None:
        models = []
        
    try:
        await init_beanie(
            connection_string=settings.MONGO_URI,
            document_models=models,
            allow_index_dropping=True
        )
        logger.info("Successfully connected to MongoDB and initialized Beanie")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise e
