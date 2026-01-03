from typing import Optional
from pydantic import BaseModel


class CandleOutDTO(BaseModel):
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
    is_closed: bool
    cfg_hash: Optional[str] = None
