# core/usecases/backfill_candles_use_case.py
from __future__ import annotations

import logging
from typing import Any, List, Optional

from adapters.external.binance.binance_rest_client import BinanceRestClient  # type: ignore
from core.domain.entities.candle_entity import CandleEntity
from core.repositories.candle_repository import CandleRepository
from core.repositories.processing_offset_repository import ProcessingOffsetRepository


class BackfillCandlesUseCase:
    """
   Backfills closed candles after the last known offset for a given stream.
    """

    def __init__(
        self,
        binance_client: BinanceRestClient,
        candle_repository: CandleRepository,
        processing_offset_repository: ProcessingOffsetRepository,
        logger: Optional[logging.Logger] = None,
    ):
        self._binance = binance_client
        self._candles = candle_repository
        self._offsets = processing_offset_repository
        self._logger = logger or logging.getLogger(self.__class__.__name__)

    async def execute_for_symbol(self, *, source: str, symbol: str, interval: str) -> None:
        """
        Backfill candles for a (source, symbol, interval) stream based on stored offsets.
        """
        symbol_upper = symbol.upper()
        interval = str(interval)
        stream_key = self._build_stream_key(source=source, symbol=symbol, interval=interval)

        interval_ms = self._interval_to_ms(interval)
        if interval_ms is None:
            return

        offset_ent = await self._offsets.get_by_stream(stream_key)
        last_open_time: Optional[int] = None
        if offset_ent is not None:
            last_open_time = int(offset_ent.last_closed_open_time)

        if last_open_time is None:
            self._logger.info("No existing offset for %s; skipping backfill.", stream_key)
            return

        start_time = last_open_time + interval_ms
        if start_time <= 0:
            return

        limit = 1000
        while True:
            klines: List[List[Any]] = await self._binance.get_klines(
                symbol=symbol_upper,
                interval=interval,
                start_time=start_time,
                end_time=None,
                limit=limit,
            )

            if not klines:
                break

            last_batch_open_time: Optional[int] = None

            for k in klines:
                open_time = int(k[0])
                close_time = int(k[6])
                o = float(k[1])
                h = float(k[2])
                l = float(k[3])
                c = float(k[4])
                v = float(k[5])
                trades = int(k[8]) if len(k) > 8 else 0

                candle = CandleEntity(
                    stream_key=stream_key,
                    source=str(source),
                    symbol=symbol_upper,
                    interval=interval,
                    open_time=open_time,
                    close_time=close_time,
                    open=o,
                    high=h,
                    low=l,
                    close=c,
                    volume=v,
                    trades=trades,
                    is_closed=True,
                )

                await self._candles.upsert_closed_candle(candle)
                await self._offsets.set_last_closed_open_time(stream_key, open_time)
                last_batch_open_time = open_time

            if last_batch_open_time is None:
                break

            start_time = last_batch_open_time + interval_ms
            if len(klines) < limit:
                break

    @staticmethod
    def _interval_to_ms(interval: str) -> Optional[int]:
        """
        Convert supported intervals to milliseconds.
        """
        return {"1m": 60_000}.get(interval)

    @staticmethod
    def _build_stream_key(*, source: str, symbol: str, interval: str) -> str:
        """
        Build a canonical stream key for multi-source ingestion.
        """
        return f"{source.lower()}:{symbol.lower()}_{interval}"
