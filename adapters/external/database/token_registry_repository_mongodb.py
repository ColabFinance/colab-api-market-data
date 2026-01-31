from __future__ import annotations

from typing import List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from core.domain.entities.token_registry_entity import TokenRegistryEntity
from core.repositories.token_registry_repository import TokenRegistryRepository


class TokenRegistryRepositoryMongoDB(TokenRegistryRepository):
    """
    MongoDB repository for token registry.

    Identity:
      (chain, token_address)
    """

    COLLECTION = "token_registry"

    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db

    async def ensure_indexes(self) -> None:
        col = self._db[self.COLLECTION]
        await col.create_index([("chain", 1), ("token_address", 1)], unique=True)
        await col.create_index([("pool_address", 1)])

    async def upsert(self, token: TokenRegistryEntity) -> None:
        col = self._db[self.COLLECTION]
        key = {"chain": token.chain, "token_address": token.token_address}
        await col.update_one(key, {"$set": token.to_mongo()}, upsert=True)

    async def get_by_token_address(self, *, chain: str, token_address: str) -> TokenRegistryEntity | None:
        col = self._db[self.COLLECTION]
        doc = await col.find_one({"chain": str(chain).strip().lower(), "token_address": str(token_address).strip().lower()})
        return TokenRegistryEntity.from_mongo(doc) if doc else None

    async def list_all(self, *, chain: Optional[str] = None) -> List[TokenRegistryEntity]:
        col = self._db[self.COLLECTION]
        q = {}
        if chain:
            q["chain"] = str(chain).strip().lower()
        docs = await col.find(q).to_list(length=50_000)
        out = [TokenRegistryEntity.from_mongo(d) for d in docs]
        return [x for x in out if x is not None]
