from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from core.domain.entities.token_registry_entity import TokenRegistryEntity


class TokenRegistryRepository(ABC):
    """
    Abstraction for token registry used by on-demand pricing endpoints.
    """

    @abstractmethod
    async def upsert(self, token: TokenRegistryEntity) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_token_address(self, *, chain: str, token_address: str) -> Optional[TokenRegistryEntity]:
        raise NotImplementedError

    @abstractmethod
    async def list_all(self, *, chain: Optional[str] = None) -> List[TokenRegistryEntity]:
        raise NotImplementedError
