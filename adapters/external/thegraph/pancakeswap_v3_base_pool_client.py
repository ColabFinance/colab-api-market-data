from __future__ import annotations

from typing import Any, Dict, Optional

from adapters.external.thegraph.thegraph_http_client import TheGraphHttpClient
from config.settings import settings


class PancakeSwapV3BasePoolClient:
    """
    Client for PancakeSwap V3 on Base via The Graph Gateway.

    Default subgraph id is configured in settings:
      settings.THEGRAPH_PANCAKESWAP_V3_BASE_SUBGRAPH_ID
    """

    def __init__(
        self,
        *,
        api_key: str,
        timeout_s: Optional[float] = None,
        subgraph_id: Optional[str] = None,
        endpoint: Optional[str] = None,
    ) -> None:
        sg = (subgraph_id or settings.THEGRAPH_PANCAKESWAP_V3_BASE_SUBGRAPH_ID).strip()
        ep = (endpoint or f"{settings.THEGRAPH_GATEWAY_BASE_URL}{sg}").strip()
        self._http = TheGraphHttpClient(
            endpoint=ep,
            api_key=api_key,
            timeout_s=float(timeout_s or settings.THEGRAPH_DEFAULT_TIMEOUT_S),
            connect_timeout_s=float(settings.THEGRAPH_HTTP_CONNECT_TIMEOUT_S),
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def get_pool(self, *, pool_address: str) -> Dict[str, Any]:
        """
        Fetch pool state by address.

        Note:
        - Schema fields may vary across subgraphs; this query uses common V3 fields.
        - If a field is missing, it will just not exist in the response.
        """
        q = """
        query Pool($id: ID!) {
          pool(id: $id) {
            id
            feeTier
            liquidity
            sqrtPrice
            tick
            token0Price
            token1Price
            volumeUSD
            totalValueLockedUSD
            token0 { id symbol decimals }
            token1 { id symbol decimals }
          }
        }
        """
        pool_id = str(pool_address).lower().strip()
        res = await self._http.query(query=q, variables={"id": pool_id})
        return (res or {}).get("data", {}).get("pool") or {}
