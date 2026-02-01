from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


def _norm_addr(v: str) -> str:
    v = (v or "").strip().lower()
    if not v:
        raise ValueError("field is required")
    if not v.startswith("0x") or len(v) != 42:
        raise ValueError("invalid_evm_address")
    return v


class TokenRegisterFromPoolDTO(BaseModel):
    """
    Register a token pricing source using a V3 pool address.

    - token_address must be one side of the pool
    - quote token is derived from the other side
    """

    chain: str = Field(default="base")
    dex: str = Field(default="pancakeswap_v3")

    token_address: str
    pool_address: str

    subgraph_id: Optional[str] = Field(default=None, description="Optional override subgraph id")
    quote_token_is_usd_stable: Optional[bool] = Field(
        default=None,
        description="If omitted, it is inferred by quote symbol (USD_STABLE_SYMBOLS).",
    )

    @field_validator("chain", "dex")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("field is required")
        return v.lower()

    @field_validator("token_address", "pool_address")
    @classmethod
    def _addr(cls, v: str) -> str:
        return _norm_addr(v)

    @field_validator("subgraph_id")
    @classmethod
    def _subgraph(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None


class TokenRegistryOutDTO(BaseModel):
    chain: str
    dex: str

    token_address: str
    pool_address: str
    subgraph_id: Optional[str] = None

    token0_address: str
    token1_address: str
    token0_symbol: Optional[str] = None
    token1_symbol: Optional[str] = None
    token0_decimals: Optional[int] = None
    token1_decimals: Optional[int] = None

    quote_token_address: str
    quote_token_symbol: Optional[str] = None
    quote_token_is_usd_stable: bool


class TokenPriceOutDTO(BaseModel):
    chain: str
    token_address: str

    price_usd: str = Field(..., description="Decimal string")
    quote_token_address: str
    quote_token_is_usd_stable: bool
    price_in_quote: str = Field(..., description="Decimal string")
    pool_address: str

    decimals: int = Field(..., description="Token decimals (from registry/pool)")