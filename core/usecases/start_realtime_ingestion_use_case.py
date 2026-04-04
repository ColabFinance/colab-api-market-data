from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from adapters.external.binance.binance_websocket_client import BinanceWebsocketClient
from adapters.external.redis.trade_candle_stream_publisher import TradeCandleStreamPublisher
from adapters.external.signals.signals_http_client import SignalsHttpClient
from core.domain.entities.candle_entity import CandleEntity
from core.repositories.candle_repository import CandleRepository
from core.repositories.indicator_set_repository import IndicatorSetRepository
from core.repositories.processing_offset_repository import ProcessingOffsetRepository
from core.usecases.compute_indicators_use_case import ComputeIndicatorsUseCase


class StartRealtimeIngestionUseCase:
    """
    Start realtime ingestion from a websocket source and persist closed candles.

    This use case now supports two downstream notification flows:
    - trade candle publication through Redis Streams
    - indicator-based LP candle-closed notifications through HTTP
    """

    def __init__(
        self,
        *,
        stream_key: str,
        source: str,
        symbol: str,
        interval: str,
        websocket_client: BinanceWebsocketClient,
        candle_repository: CandleRepository,
        processing_offset_repository: ProcessingOffsetRepository,
        compute_indicators_use_case: Optional[ComputeIndicatorsUseCase] = None,
        indicator_set_repo: Optional[IndicatorSetRepository] = None,
        logger: logging.Logger | None = None,
        signals_client: Optional[SignalsHttpClient] = None,
        trade_candle_publisher: Optional[TradeCandleStreamPublisher] = None,
    ):
        """
        Initialize the realtime ingestion use case.

        Args:
            stream_key: Canonical stream identifier.
            source: Source label, such as binance.
            symbol: Trading symbol, such as BTCUSDT.
            interval: Candle interval, such as 1m.
            websocket_client: Websocket client used to receive kline events.
            candle_repository: Candle persistence repository.
            processing_offset_repository: Offset repository for last processed candle.
            compute_indicators_use_case: Optional indicator computation use case.
            indicator_set_repo: Optional repository of active indicator sets.
            logger: Optional logger instance.
            signals_client: Optional HTTP client used for LP indicator notifications.
            trade_candle_publisher: Optional Redis Stream publisher used for trade candles.
        """
        self._source = str(source).lower()
        self._symbol = symbol.upper()
        self._interval = str(interval)
        self._ws = websocket_client
        self._candle_repo = candle_repository
        self._offset_repo = processing_offset_repository
        self._compute_indicators = compute_indicators_use_case
        self._indicator_set_repo = indicator_set_repo
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self._stream_key = str(stream_key)
        self._lp_signals_client = signals_client
        self._trade_candle_publisher = trade_candle_publisher
        self._background_tasks: set[asyncio.Task] = set()

    async def execute(self) -> None:
        """
        Start websocket subscription and register the closed-kline callback.
        """
        self._logger.info(
            "Starting realtime ingestion for source=%s symbol=%s interval=%s stream_key=%s",
            self._source,
            self._symbol,
            self._interval,
            self._stream_key,
        )
        await self._ws.subscribe_kline_1m(self._symbol, self._on_kline_closed)

    async def _on_kline_closed(self, event: Dict[str, Any]) -> None:
        """
        Handle a single closed-kline event.

        The method persists the closed candle, updates the processing offset,
        publishes the trade candle to Redis Streams, and then computes and
        emits indicator-based triggers for LP flows.
        """
        try:
            k = event["k"]

            candle = CandleEntity(
                stream_key=self._stream_key,
                source=self._source,
                symbol=str(event["s"]).upper(),
                interval=str(k["i"]),
                open_time=int(k["t"]),
                close_time=int(k["T"]),
                open=float(k["o"]),
                high=float(k["h"]),
                low=float(k["l"]),
                close=float(k["c"]),
                volume=float(k["v"]),
                trades=int(k["n"]),
                is_closed=True,
            )

            await self._candle_repo.upsert_closed_candle(candle)
            await self._offset_repo.set_last_closed_open_time(self._stream_key, candle.open_time)

            if self._trade_candle_publisher is not None:
                await self._trade_candle_publisher.publish_closed_candle(candle)

            if self._compute_indicators is None or self._indicator_set_repo is None:
                return

            active_sets = await self._indicator_set_repo.get_active_by_stream(self._stream_key)
            for indset in active_sets:
                indicator_snapshot = await self._compute_indicators.execute_for_indicator_set(
                    stream_key=self._stream_key,
                    ema_fast=int(indset.ema_fast),
                    ema_slow=int(indset.ema_slow),
                    atr_window=int(indset.atr_window),
                    indicator_set_id=indset.cfg_hash,
                    cfg_hash=indset.cfg_hash,
                    ts=candle.close_time,
                )

                if self._lp_signals_client is not None and indicator_snapshot is not None:
                    self._create_background_task(
                        self._notify_lp_candle_closed_safe(
                            indicator_set_id=indset.cfg_hash,
                            ts=candle.close_time,
                            indicator_set=indset.to_dict(),
                            indicator_snapshot=indicator_snapshot.to_dict(),
                        )
                    )

        except Exception as exc:
            self._logger.exception("Failed to process closed kline for stream_key=%s: %s", self._stream_key, exc)

    def _create_background_task(self, coro: asyncio.Future | asyncio.coroutines) -> None:
        """
        Create and track a background task safely.
        """
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _notify_lp_candle_closed_safe(
        self,
        *,
        indicator_set_id: str,
        ts: int,
        indicator_set: Dict[str, Any],
        indicator_snapshot: Dict[str, Any],
    ) -> None:
        """
        Notify api-signals about an LP candle close using a safe background task.

        This method captures transport errors so they do not become
        unhandled asyncio task exceptions.
        """
        if self._lp_signals_client is None:
            return

        max_attempts = 3
        retry_delays_s = (0.5, 1.0, 2.0)

        for attempt in range(1, max_attempts + 1):
            try:
                await self._lp_signals_client.candle_closed(
                    indicator_set_id=indicator_set_id,
                    ts=ts,
                    indicator_set=indicator_set,
                    indicator_snapshot=indicator_snapshot,
                )
                return
            except Exception as exc:
                if attempt >= max_attempts:
                    self._logger.exception(
                        "Failed notifying LP candle_closed after retries. indicator_set_id=%s ts=%s err=%s",
                        indicator_set_id,
                        ts,
                        exc,
                    )
                    return

                delay_s = retry_delays_s[min(attempt - 1, len(retry_delays_s) - 1)]
                self._logger.warning(
                    "LP candle_closed notification failed. Retrying... indicator_set_id=%s ts=%s attempt=%s/%s delay_s=%s err=%s",
                    indicator_set_id,
                    ts,
                    attempt,
                    max_attempts,
                    delay_s,
                    exc,
                )
                await asyncio.sleep(delay_s)