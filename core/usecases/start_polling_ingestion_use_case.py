from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from adapters.external.signals.signals_http_client import SignalsHttpClient
from core.domain.entities.candle_entity import CandleEntity
from core.repositories.candle_repository import CandleRepository
from core.repositories.indicator_set_repository import IndicatorSetRepository
from core.usecases.compute_indicators_use_case import ComputeIndicatorsUseCase


class StartPollingIngestionUseCase:
    """
    Start a polling-based ingestion loop and persist synthetic closed candles.

    This use case supports two downstream notification flows:
    - generic stream-based trade candle-closed notifications
    - indicator-based LP candle-closed notifications
    """

    def __init__(
        self,
        *,
        stream_key: str,
        source: str,
        symbol: str,
        interval: str,
        poll_every_s: float,
        candle_repository: CandleRepository,
        processing_offset_repository: Any,
        fetch_fn,
        compute_indicators_use_case: Optional[ComputeIndicatorsUseCase] = None,
        indicator_set_repo: Optional[IndicatorSetRepository] = None,
        signals_client: Optional[SignalsHttpClient] = None,
        logger: logging.Logger | None = None,
        static_candle_fields: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the polling ingestion use case.

        Args:
            stream_key: Canonical stream identifier.
            source: Source label.
            symbol: Traded symbol or synthetic symbol.
            interval: Candle interval.
            poll_every_s: Polling frequency in seconds.
            candle_repository: Candle persistence repository.
            processing_offset_repository: Optional future offset repository.
            fetch_fn: Async function that fetches the latest price/state.
            compute_indicators_use_case: Optional indicator computation use case.
            indicator_set_repo: Optional repository of active indicator sets.
            signals_client: Optional HTTP client used to notify api-signals.
            logger: Optional logger instance.
            static_candle_fields: Optional static fields merged into stored candles.
        """
        self._stream_key = str(stream_key)
        self._source = str(source)
        self._symbol = str(symbol)
        self._interval = str(interval)
        self._poll_every_s = float(poll_every_s)
        self._candle_repo = candle_repository
        self._offset_repo = processing_offset_repository
        self._fetch_fn = fetch_fn
        self._compute_indicators = compute_indicators_use_case
        self._indicator_set_repo = indicator_set_repo
        self._signals_client = signals_client
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self._static_fields = static_candle_fields or {}

        self._task: asyncio.Task | None = None
        self._last_close: Optional[float] = None

    async def start(self) -> None:
        """
        Start the polling loop as a background asyncio task.
        """
        if self._task and not self._task.done():
            return

        async def _loop() -> None:
            """
            Internal polling loop task.
            """
            self._logger.info(
                "Starting polling ingestion stream_key=%s poll_every_s=%s",
                self._stream_key,
                self._poll_every_s,
            )
            while True:
                try:
                    await self._tick_once()
                except Exception as exc:
                    self._logger.exception("Polling ingestion tick failed stream_key=%s: %s", self._stream_key, exc)
                await asyncio.sleep(self._poll_every_s)

        self._task = asyncio.create_task(_loop())

    async def stop(self) -> None:
        """
        Stop the polling loop task.
        """
        if self._task:
            self._task.cancel()
            self._task = None

    async def _tick_once(self) -> None:
        """
        Fetch the latest market state, build a synthetic closed candle,
        persist it, and notify downstream services.
        """
        fetched: Dict[str, Any] = await self._fetch_fn()
        price = float(fetched["price"])

        now = datetime.now(tz=timezone.utc)
        close_time = int(now.replace(second=0, microsecond=0).timestamp() * 1000)
        open_time = close_time - 60_000

        open_price = float(self._last_close) if self._last_close is not None else price
        high_price = max(open_price, price)
        low_price = min(open_price, price)

        candle = CandleEntity(
            stream_key=self._stream_key,
            source=self._source,
            symbol=self._symbol,
            interval=self._interval,
            open_time=open_time,
            close_time=close_time,
            open=open_price,
            high=high_price,
            low=low_price,
            close=price,
            volume=float(fetched.get("volume", 0.0) or 0.0),
            trades=int(fetched.get("trades", 0) or 0),
            is_closed=True,
            raw_event_id=str(fetched.get("raw_event_id") or ""),
        )

        for key, value in (fetched.get("candle_fields") or {}).items():
            setattr(candle, key, value)

        for key, value in self._static_fields.items():
            setattr(candle, key, value)

        await self._candle_repo.upsert_closed_candle(candle)
        self._last_close = price

        if self._compute_indicators is None or self._indicator_set_repo is None:
            return

        active_sets = await self._indicator_set_repo.get_active_by_stream(self._stream_key)
        for indset in active_sets:
            snapshot = await self._compute_indicators.execute_for_indicator_set(
                stream_key=self._stream_key,
                ema_fast=int(indset.ema_fast),
                ema_slow=int(indset.ema_slow),
                atr_window=int(indset.atr_window),
                indicator_set_id=indset.cfg_hash,
                cfg_hash=indset.cfg_hash,
                ts=close_time,
            )
            if self._signals_client is not None and snapshot is not None:
                asyncio.create_task(
                    self._signals_client.candle_closed(
                        indicator_set_id=indset.cfg_hash,
                        ts=close_time,
                        indicator_set=indset.to_dict(),
                        indicator_snapshot=snapshot.to_dict(),
                    )
                )