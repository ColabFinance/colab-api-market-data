from typing import Optional
from pydantic import BaseModel


class IndicatorSnapshotOutDTO(BaseModel):
    symbol: str
    interval: str
    ts: int
    close: float
    ema_fast: float
    ema_slow: float
    atr_pct: float
    indicator_set_id: Optional[str] = None
    cfg_hash: Optional[str] = None
    created_at_iso: Optional[str] = None
