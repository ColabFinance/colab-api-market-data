from __future__ import annotations

import logging
from typing import Dict

from redis.asyncio import Redis

from core.domain.entities.candle_entity import CandleEntity


class TradeCandleStreamPublisher:
    """
    Publish closed trade candles to Redis Streams.
    """

    def __init__(
        self,
        *,
        redis_client: Redis,
        stream_name: str,
        maxlen: int,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Initialize the trade candle publisher.
        """
        self._redis = redis_client
        self._stream_name = str(stream_name).strip()
        self._maxlen = int(maxlen)
        self._logger = logger or logging.getLogger(self.__class__.__name__)

    async def publish_closed_candle(self, candle: CandleEntity) -> str:
        """
        Publish a closed candle event to the configured Redis Stream.
        """
        payload = self._build_payload(candle)
        message_id = await self._redis.xadd(
            self._stream_name,
            payload,
            maxlen=self._maxlen,
            approximate=True,
        )
        self._logger.debug(
            "Published trade candle to Redis Stream. stream=%s message_id=%s stream_key=%s ts=%s",
            self._stream_name,
            message_id,
            candle.stream_key,
            candle.close_time,
        )
        return str(message_id)

    def _build_payload(self, candle: CandleEntity) -> Dict[str, str]:
        """
        Build a flat Redis Stream payload from a candle entity.
        """
        return {
            "event_type": "trade.candle.closed",
            "event_version": "1",
            "stream_key": str(candle.stream_key).strip().lower(),
            "ts": str(int(candle.close_time)),
            "source": str(candle.source).strip().lower(),
            "symbol": str(candle.symbol).strip().upper(),
            "interval": str(candle.interval).strip().lower(),
            "open_time": str(int(candle.open_time)),
            "close_time": str(int(candle.close_time)),
            "open": str(float(candle.open)),
            "high": str(float(candle.high)),
            "low": str(float(candle.low)),
            "close": str(float(candle.close)),
            "volume": str(float(candle.volume)),
            "trades": str(int(candle.trades)),
            "is_closed": "1" if bool(candle.is_closed) else "0",
        }