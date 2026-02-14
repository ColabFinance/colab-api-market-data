# core/repositories/indicator_set_repository.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from core.domain.entities.indicator_set_entity import IndicatorSetEntity


class IndicatorSetRepository(ABC):
    """
   Persistence interface for indicator-set configurations.
    """

    @abstractmethod
    async def ensure_indexes(self) -> None:
        """Ensure all required indexes exist."""
        raise NotImplementedError

    @abstractmethod
    async def upsert_active(self, indset: IndicatorSetEntity) -> IndicatorSetEntity:
        """Upsert (create/update) an ACTIVE indicator set."""
        raise NotImplementedError

    @abstractmethod
    async def get_active_by_stream(self, stream_key: str) -> List[IndicatorSetEntity]:
        """Get all ACTIVE indicator sets for a stream_key."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, cfg_hash: str) -> Optional[IndicatorSetEntity]:
        """Get an indicator set by cfg_hash."""
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError