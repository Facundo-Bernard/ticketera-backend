import asyncio
import logging
from typing import List, Type
from beanie import init_beanie, Document
from .settings import settings

logger = logging.getLogger(__name__)

async def init_db(models: List[Type[Document]] = None, max_retries: int = 5, retry_delay: float = 2.0):
    if models is None:
        models = []

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Attempting to connect to MongoDB ({attempt}/{max_retries})...")
            await init_beanie(
                connection_string=settings.MONGO_URI,
                document_models=models,
                allow_index_dropping=True
            )
            logger.info("Successfully connected to MongoDB and initialized Beanie")
            return
        except Exception as e:
            logger.warning(f"Failed to connect to MongoDB (attempt {attempt}/{max_retries}): {e}")
            if attempt == max_retries:
                logger.error("Exceeded maximum retries connecting to MongoDB.")
                raise e
            await asyncio.sleep(retry_delay)
