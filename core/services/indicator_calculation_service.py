# core/services/indicator_calculation_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from core.domain.entities.candle_entity import CandleEntity
from core.domain.entities.indicator_entity import IndicatorSnapshotEntity


class IndicatorCalculationService:
    """
   Pure calculation service for indicator snapshots (no I/O).
    """

    def compute_snapshot_for_last(
        self,
        candles: List[CandleEntity],
        *,
        ema_fast: int,
        ema_slow: int,
        atr_window: int,
        indicator_set_id: str,
        cfg_hash: str,
    ) -> Optional[IndicatorSnapshotEntity]:
        """
        Compute indicators (EMA fast/slow and ATR%) for the last candle.

        Args:
            candles: Closed candles in ascending open_time order.
            ema_fast: EMA fast period.
            ema_slow: EMA slow period.
            atr_window: ATR window length.
            indicator_set_id: Indicator set identifier.
            cfg_hash: Config hash.

        Returns:
            A typed snapshot entity or None if not enough candles.
        """
        if not candles:
            return None

        need = max(int(ema_slow), int(atr_window))
        if len(candles) < need:
            return None

        closes = [float(c.close) for c in candles]
        highs = [float(c.high) for c in candles]
        lows = [float(c.low) for c in candles]

        ema_f = self._ema(closes, int(ema_fast))
        ema_s = self._ema(closes, int(ema_slow))
        atr = self._atr(highs, lows, closes, int(atr_window))

        last = candles[-1]
        close = float(last.close)

        atr_pct = 0.0
        if close > 0 and atr is not None:
            atr_pct = float(atr) / close

        created_at_iso = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")

        return IndicatorSnapshotEntity(
            stream_key=last.stream_key,
            source=last.source,
            symbol=str(last.symbol).upper(),
            interval=str(last.interval),
            ts=int(last.close_time),
            close=float(close),
            ema_fast=float(ema_f) if ema_f is not None else 0.0,
            ema_slow=float(ema_s) if ema_s is not None else 0.0,
            atr_pct=float(atr_pct),
            indicator_set_id=str(indicator_set_id),
            cfg_hash=str(cfg_hash),
            created_at_iso=created_at_iso,
        )

    def _ema(self, values: List[float], period: int) -> Optional[float]:
        """
        Compute EMA for the last value in the series.
        """
        if period <= 0 or len(values) < period:
            return None
        k = 2.0 / (period + 1.0)
        ema = sum(values[:period]) / float(period)
        for v in values[period:]:
            ema = (v - ema) * k + ema
        return ema

    def _atr(self, highs: List[float], lows: List[float], closes: List[float], period: int) -> Optional[float]:
        """
        Compute a simple ATR (SMA of true range) over the last `period` TRs.
        """
        if period <= 0 or len(closes) < period + 1:
            return None
        trs: List[float] = []
        for i in range(1, len(closes)):
            h = highs[i]
            l = lows[i]
            prev_c = closes[i - 1]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            trs.append(tr)

        window = trs[-period:]
        return sum(window) / float(period)
