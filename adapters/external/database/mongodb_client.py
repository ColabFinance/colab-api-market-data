# adapters/external/database/mongodb_client.py
from motor.motor_asyncio import AsyncIOMotorClient

from config.settings import settings


def get_mongo_client() -> AsyncIOMotorClient:
    """
   Create a MongoDB async client using the configured connection string.
    """
    return AsyncIOMotorClient(settings.MONGODB_URL)
