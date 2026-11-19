import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Type
from beanie import init_beanie, Document
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from .settings import settings

logger = logging.getLogger(__name__)

_motor_clients: Dict[Tuple[str, int], AsyncIOMotorClient] = {}


def get_motor_database(
    mongo_uri: Optional[str] = None,
    db_name: Optional[str] = None,
) -> AsyncIOMotorDatabase:
    """Retorna una instancia reutilizable de base de datos Motor asociada al loop activo."""
    uri = mongo_uri or settings.MONGO_URI
    target_db = db_name or settings.MONGO_DB_NAME
    loop = asyncio.get_running_loop()
    cache_key = (uri, id(loop))

    # Limpiar clientes cuyo event loop ya fue cerrado (p.ej. entre módulos de TestClient)
    for key in list(_motor_clients.keys()):
        client_loop = getattr(_motor_clients[key], "io_loop", None)
        if client_loop is not None and client_loop.is_closed():
            _motor_clients.pop(key, None)

    client = _motor_clients.get(cache_key)
    if client is None:
        client = AsyncIOMotorClient(uri)
        _motor_clients[cache_key] = client
    return client[target_db]

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
