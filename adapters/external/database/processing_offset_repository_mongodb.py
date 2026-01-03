# adapters/external/database/processing_offset_repository_mongodb.py
from __future__ import annotations

from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from core.domain.entities.processing_offset_entity import ProcessingOffsetEntity
from core.repositories.processing_offset_repository import ProcessingOffsetRepository


class ProcessingOffsetRepositoryMongoDB(ProcessingOffsetRepository):
    """
   MongoDB implementation for stream offsets.
    """

    COLLECTION = "processing_offsets"

    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Args:
            db: Motor database handle.
        """
        self._db = db

    async def ensure_indexes(self) -> None:
        """
        Ensure uniqueness by stream_key.
        """
        col = self._db[self.COLLECTION]
        await col.create_index([("stream_key", 1)], unique=True)

    async def get_by_stream(self, stream_key: str) -> Optional[ProcessingOffsetEntity]:
        """
        Get the offset entity for a stream_key.
        """
        col = self._db[self.COLLECTION]
        doc = await col.find_one({"stream_key": stream_key})
        return ProcessingOffsetEntity.from_mongo(doc)

    async def set_last_closed_open_time(self, stream_key: str, open_time: int) -> None:
        """
        Upsert last_closed_open_time for a stream_key.
        """
        col = self._db[self.COLLECTION]
        ent = ProcessingOffsetEntity(stream_key=stream_key, last_closed_open_time=int(open_time))
        await col.update_one(
            {"stream_key": stream_key},
            {"$set": ent.to_mongo()},
            upsert=True,
        )
