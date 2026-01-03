# adapters/external/database/indicator_repository_mongodb.py
from __future__ import annotations

from typing import List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from core.domain.entities.indicator_entity import IndicatorSnapshotEntity
from core.repositories.indicator_repository import IndicatorRepository


class IndicatorRepositoryMongoDB(IndicatorRepository):
    """
   MongoDB implementation for indicator snapshot persistence.
    """

    COLLECTION = "indicators_1m"

    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Args:
            db: Motor database handle.
        """
        self._db = db

    async def ensure_indexes(self) -> None:
        """
        Ensure uniqueness by (stream_key, ts, cfg_hash) and allow efficient recent queries.
        """
        col = self._db[self.COLLECTION]
        await col.create_index([("stream_key", 1), ("ts", 1), ("cfg_hash", 1)], unique=True)
        await col.create_index([("stream_key", 1), ("ts", -1)])
        await col.create_index([("stream_key", 1), ("cfg_hash", 1), ("ts", -1)])

    async def upsert_snapshot(self, snapshot: IndicatorSnapshotEntity) -> None:
        """
        Upsert a snapshot by (stream_key, ts, cfg_hash).
        """
        col = self._db[self.COLLECTION]
        doc = snapshot.to_mongo()
        key = {
            "stream_key": snapshot.stream_key,
            "ts": int(snapshot.ts),
            "cfg_hash": snapshot.cfg_hash,
        }
        await col.update_one(key, {"$set": doc}, upsert=True)

    async def list_last(
        self,
        stream_key: str,
        cfg_hash: Optional[str],
        limit: int,
    ) -> List[IndicatorSnapshotEntity]:
        """
        List the last snapshots for a stream_key (and optional cfg_hash), ascending by ts.
        """
        col = self._db[self.COLLECTION]
        q: dict[str, object] = {"stream_key": stream_key}
        if cfg_hash:
            q["cfg_hash"] = cfg_hash

        cursor = col.find(q).sort("ts", -1).limit(int(limit))
        docs = await cursor.to_list(length=int(limit))
        entities = [IndicatorSnapshotEntity.from_mongo(d) for d in docs]
        out = [e for e in entities if e is not None]
        out.reverse()
        return out
