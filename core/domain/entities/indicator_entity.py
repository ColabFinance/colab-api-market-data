# core/domain/entities/indicator_entity.py
from __future__ import annotations

from core.domain.entities.base_entity import MongoEntity


class IndicatorSnapshotEntity(MongoEntity):
    """
   Computed indicator snapshot for a specific candle timestamp and config.

    `stream_key` ties the snapshot to the same stream that produced the candles.
    """

    stream_key: str
    source: str

    symbol: str
    interval: str

    ts: int  # typically candle close_time (ms)
    close: float

    ema_fast: float
    ema_slow: float
    atr_pct: float

    indicator_set_id: str
    cfg_hash: str
