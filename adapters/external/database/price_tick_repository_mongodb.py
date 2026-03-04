from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from motor.motor_asyncio import AsyncIOMotorDatabase

from core.domain.entities.price_tick_entity import PriceTickEntity
from core.repositories.price_tick_repository import PriceTickRepository


class PriceTickRepositoryMongoDB(PriceTickRepository):
    """
    MongoDB repository for high-frequency ticks.

    Collection is separate from candles to avoid write amplification on candles_1m
    and to allow fast aggregation per minute.
    """

    COLLECTION = "price_ticks"

    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db

    async def ensure_indexes(self) -> None:
        col = self._db[self.COLLECTION]

        # Fast range queries for building a candle
        await col.create_index([("stream_key", 1), ("minute_open_time", 1), ("ts", 1)])

        # Fast range queries for episode/tick analytics (APR in-range time)
        await col.create_index([("stream_key", 1), ("ts", 1)])

    async def insert_tick(self, tick: PriceTickEntity) -> None:
        now_iso = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
        tick.created_at_iso = now_iso

        col = self._db[self.COLLECTION]
        payload = tick.to_mongo()

        # do NOT upsert by minute: we want every sample tick
        await col.insert_one(payload)

    async def list_ticks_for_minute(self, stream_key: str, minute_open_time: int) -> List[PriceTickEntity]:
        col = self._db[self.COLLECTION]
        cur = (
            col.find({"stream_key": stream_key, "minute_open_time": int(minute_open_time)})
            .sort("ts", 1)
        )
        docs = await cur.to_list(length=10_000)
        return [PriceTickEntity.from_mongo(d) for d in docs if d]

    async def list_ticks_range(
        self,
        stream_key: str,
        ts_from: int,
        ts_to: int,
        limit: int = 5000,
    ) -> List[PriceTickEntity]:
        col = self._db[self.COLLECTION]
        cur = (
            col.find(
                {
                    "stream_key": str(stream_key),
                    "ts": {"$gte": int(ts_from), "$lte": int(ts_to)},
                }
            )
            .sort("ts", 1)
            .limit(int(limit))
        )
        docs = await cur.to_list(length=int(limit))
        return [PriceTickEntity.from_mongo(d) for d in docs if d]

    async def delete_ticks_for_minute(self, stream_key: str, minute_open_time: int) -> None:
        col = self._db[self.COLLECTION]
        await col.delete_many({"stream_key": stream_key, "minute_open_time": int(minute_open_time)})