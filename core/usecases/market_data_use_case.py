from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from core.domain.entities.candle_entity import CandleEntity
from core.domain.entities.indicator_entity import IndicatorSnapshotEntity
from core.domain.entities.indicator_set_entity import IndicatorSetEntity
from core.repositories.candle_repository import CandleRepository
from core.repositories.indicator_repository import IndicatorRepository
from core.repositories.indicator_set_repository import IndicatorSetRepository
from core.services.stream_key_service import StreamKeyService


@dataclass
class MarketDataUseCase:
    """
    Application layer for market-data reads/writes (indicator-sets, candles, indicators).

    Keeps routers thin and consistent with the rest of the project.
    """
    candle_repo: CandleRepository
    indicator_repo: IndicatorRepository
    indicator_set_repo: IndicatorSetRepository

    async def ensure_indexes(self) -> None:
        await self.candle_repo.ensure_indexes()
        await self.indicator_repo.ensure_indexes()
        await self.indicator_set_repo.ensure_indexes()

    async def upsert_active_indicator_set(
        self,
        *,
        symbol: str,
        ema_fast: int,
        ema_slow: int,
        atr_window: int,
        source: Optional[str] = "binance",
        pool_address: Optional[str] = None,
    ) -> IndicatorSetEntity:
        """
        Create (or reuse) an ACTIVE indicator set.

        Idempotency is guaranteed by cfg_hash (derived from stream_key + params).
        """
        interval = "1m"
        src = (source or "binance").lower().strip()

        stream_key = StreamKeyService.build(
            source=src,
            symbol=symbol,
            interval=interval,
            pool_address=pool_address,
        )

        ent = IndicatorSetEntity(
            stream_key=stream_key,
            source=src,
            symbol=symbol,
            interval=interval,
            ema_fast=int(ema_fast),
            ema_slow=int(ema_slow),
            atr_window=int(atr_window),
            status="ACTIVE",
            pool_address=(pool_address.lower().strip() if pool_address else None),
        )

        stored = await self.indicator_set_repo.upsert_active(ent)
        return stored

    async def get_indicator_set(self, *, cfg_hash: str) -> Optional[IndicatorSetEntity]:
        return await self.indicator_set_repo.get_by_id(cfg_hash)

    async def list_indicator_sets(
        self,
        *,
        stream_key: Optional[str] = None,
        status: Optional[str] = "ACTIVE",
        limit: int = 5000,
    ) -> List[IndicatorSetEntity]:
        if stream_key and (status or "").upper() == "ACTIVE":
            return await self.indicator_set_repo.get_active_by_stream(stream_key)
        return await self.indicator_set_repo.filter(stream_key=stream_key, status=status, limit=int(limit))

    async def list_candles(self, *, stream_key: str, limit: int) -> List[CandleEntity]:
        return await self.candle_repo.get_last_n_closed(stream_key=stream_key, n=int(limit))

    async def list_indicators(
        self,
        *,
        stream_key: str,
        cfg_hash: Optional[str],
        limit: int,
    ) -> List[IndicatorSnapshotEntity]:
        return await self.indicator_repo.list_last(stream_key=stream_key, cfg_hash=cfg_hash, limit=int(limit))
