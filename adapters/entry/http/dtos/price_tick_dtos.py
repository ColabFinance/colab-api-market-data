

from typing import Optional

from pydantic import BaseModel


class PriceTickOutDTO(BaseModel):
    stream_key: str
    ts: int
    minute_open_time: int
    price: float

    source: Optional[str] = None
    symbol: Optional[str] = None
    interval: Optional[str] = None

    extras: Optional[dict] = None

