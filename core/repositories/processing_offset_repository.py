# core/repositories/processing_offset_repository.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from core.domain.entities.processing_offset_entity import ProcessingOffsetEntity


class ProcessingOffsetRepository(ABC):
    """
   Persistence interface for per-stream offsets.
    """

    @abstractmethod
    async def ensure_indexes(self) -> None:
        """Ensure all required indexes exist."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_stream(self, stream_key: str) -> Optional[ProcessingOffsetEntity]:
        """Return the offset entity for a stream_key (or None)."""
        raise NotImplementedError

    @abstractmethod
    async def set_last_closed_open_time(self, stream_key: str, open_time: int) -> None:
        """Upsert last closed open_time for the stream_key."""
        raise NotImplementedError
