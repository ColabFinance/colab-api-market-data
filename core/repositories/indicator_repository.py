# core/repositories/indicator_repository.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from core.domain.entities.indicator_entity import IndicatorSnapshotEntity


class IndicatorRepository(ABC):
    """
   Persistence interface for computed indicator snapshots.
    """

    @abstractmethod
    async def ensure_indexes(self) -> None:
        """Ensure all required indexes exist."""
        raise NotImplementedError

    @abstractmethod
    async def upsert_snapshot(self, snapshot: IndicatorSnapshotEntity) -> None:
        """Insert/update a snapshot (idempotent)."""
        raise NotImplementedError

    @abstractmethod
    async def list_last(
        self,
        stream_key: str,
        cfg_hash: Optional[str],
        limit: int,
    ) -> List[IndicatorSnapshotEntity]:
        """List the last snapshots in ascending ts order."""
        raise NotImplementedError
