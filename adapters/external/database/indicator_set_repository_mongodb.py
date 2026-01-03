from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from core.domain.entities.indicator_set_entity import IndicatorSetEntity
from core.repositories.indicator_set_repository import IndicatorSetRepository


class IndicatorSetRepositoryMongoDB(IndicatorSetRepository):
    """
    MongoDB implementation for indicator-set configuration persistence.
    """

    COLLECTION = "indicator_sets"

    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Args:
            db: Motor database handle.
        """
        self._db = db

    async def ensure_indexes(self) -> None:
        """
        Ensure uniqueness for cfg_hash and support common filtering queries.
        """
        col = self._db[self.COLLECTION]
        await col.create_index([("cfg_hash", 1)], unique=True)
        await col.create_index([("stream_key", 1), ("status", 1)])
        await col.create_index(
            [
                ("stream_key", 1),
                ("ema_fast", 1),
                ("ema_slow", 1),
                ("atr_window", 1),
                ("status", 1),
            ]
        )

    async def upsert_active(self, indset: IndicatorSetEntity) -> IndicatorSetEntity:
        """
        Upsert an ACTIVE indicator set (creates timestamps on first insert).
        """
        col = self._db[self.COLLECTION]
        now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
        now_iso = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")

        indset = indset.normalize()
        indset.status = "ACTIVE"

        existing = await col.find_one({"cfg_hash": indset.cfg_hash})
        payload = indset.to_mongo()

        payload["updated_at"] = now_ms
        payload["updated_at_iso"] = now_iso

        if not existing:
            payload["created_at"] = now_ms
            payload["created_at_iso"] = now_iso

        await col.update_one({"cfg_hash": indset.cfg_hash}, {"$set": payload}, upsert=True)
        stored = await col.find_one({"cfg_hash": indset.cfg_hash})
        ent = IndicatorSetEntity.from_mongo(stored)
        if ent is None:
            raise RuntimeError("Failed to load indicator set after upsert.")
        return ent

    async def get_active_by_stream(self, stream_key: str) -> List[IndicatorSetEntity]:
        """
        Return all ACTIVE indicator sets for a given stream_key.
        """
        col = self._db[self.COLLECTION]
        cursor = col.find({"stream_key": stream_key, "status": "ACTIVE"})
        docs = await cursor.to_list(length=None)
        entities = [IndicatorSetEntity.from_mongo(d) for d in docs]
        return [e for e in entities if e is not None]

    async def get_by_id(self, cfg_hash: str) -> Optional[IndicatorSetEntity]:
        """
        Get an indicator set by cfg_hash.
        """
        col = self._db[self.COLLECTION]
        doc = await col.find_one({"cfg_hash": cfg_hash})
        return IndicatorSetEntity.from_mongo(doc)

    async def filter(
        self,
        *,
        stream_key: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 5000,
    ) -> List[IndicatorSetEntity]:
        """
        Filter indicator sets by optional fields.

        Args:
            stream_key: Optional stream_key filter.
            status: Optional status filter.
            limit: Max items to return.

        Returns:
            List of IndicatorSetEntity.
        """
        col = self._db[self.COLLECTION]
        q: dict[str, object] = {}
        if stream_key:
            q["stream_key"] = stream_key
        if status:
            q["status"] = str(status).upper()

        cursor = col.find(q).limit(int(limit))
        docs = await cursor.to_list(length=int(limit))
        out = [IndicatorSetEntity.from_mongo(d) for d in docs]
        return [x for x in out if x is not None]
