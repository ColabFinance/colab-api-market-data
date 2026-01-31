from __future__ import annotations

from typing import Optional

from core.domain.entities.base_entity import MongoEntity


class TokenRegistryEntity(MongoEntity):
    """
    Stores the minimum information required to resolve a token USD price on-demand using The Graph.

    Design:
    - Each token is associated to a pool address (V3 pool) that provides a spot price vs a quote token.
    - If quote token is a USD-stable, USD price is direct.
    - Otherwise, USD price is resolved by recursively pricing the quote token (which must also be registered).
    """

    chain: str = "base"
    dex: str = "pancakeswap_v3"

    token_address: str
    pool_address: str

    # Optional override (future multi-subgraph support)
    subgraph_id: Optional[str] = None

    # Cached pool metadata (filled on register)
    token0_address: str
    token1_address: str
    token0_symbol: Optional[str] = None
    token1_symbol: Optional[str] = None
    token0_decimals: Optional[int] = None
    token1_decimals: Optional[int] = None

    # Derived quote side for USD conversion
    quote_token_address: str
    quote_token_symbol: Optional[str] = None
    quote_token_is_usd_stable: bool = False
