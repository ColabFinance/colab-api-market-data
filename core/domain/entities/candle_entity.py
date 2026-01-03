# core/domain/entities/candle_entity.py
from __future__ import annotations

from typing import Optional

from core.domain.entities.base_entity import MongoEntity


class CandleEntity(MongoEntity):
    """
   Represents a closed OHLCV candle stored in MongoDB.

    `stream_key` is the canonical identifier for the ingestion stream/source + market + interval,
    e.g. "binance:btcusdt_1m".
    """

    stream_key: str
    source: str

    symbol: str
    interval: str

    open_time: int
    close_time: int

    open: float
    high: float
    low: float
    close: float

    volume: float
    trades: int
    is_closed: bool = True

    # Optional metadata for future sources
    raw_event_id: Optional[str] = None
