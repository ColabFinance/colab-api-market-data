from __future__ import annotations

from typing import Any, Dict, Optional

import httpx


class SignalsHttpClient:
    def __init__(self, *, base_url: str, timeout_s: float = 30.0):
        self._base_url = str(base_url).rstrip("/")
        self._timeout = httpx.Timeout(timeout_s, connect=5.0)

        # Reuse connections (important for high-frequency calls)
        self._client = httpx.AsyncClient(timeout=self._timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def candle_closed(
        self,
        *,
        indicator_set_id: str,
        ts: int,
        indicator_set: Optional[Dict[str, Any]] = None,
        indicator_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "indicator_set_id": indicator_set_id,
            "ts": int(ts),
            "indicator_set": indicator_set,
            "indicator_snapshot": indicator_snapshot,
        }

        r = await self._client.post(f"{self._base_url}/triggers/candle-closed", json=payload)
        r.raise_for_status()
        return r.json()
