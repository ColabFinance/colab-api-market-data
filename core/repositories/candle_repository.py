# core/repositories/candle_repository.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from core.domain.entities.candle_entity import CandleEntity


class CandleRepository(ABC):
    """
   Persistence interface for candles.
    """

    @abstractmethod
    async def ensure_indexes(self) -> None:
        """Ensure all required indexes exist."""
        raise NotImplementedError

    @abstractmethod
    async def upsert_closed_candle(self, candle: CandleEntity) -> None:
        """Insert/update a closed candle (idempotent)."""
        raise NotImplementedError

    @abstractmethod
    async def get_last_n_closed(self, stream_key: str, n: int) -> List[CandleEntity]:
        """Return the last N closed candles in ascending open_time order."""
        raise NotImplementedError
