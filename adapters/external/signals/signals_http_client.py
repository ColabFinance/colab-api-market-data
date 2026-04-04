from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx


class SignalsHttpClient:
    """
    HTTP client used by api-market-data to notify api-signals about closed-candle events.

    This client supports two trigger styles:
    - indicator-based candle closed events for the LP flow
    - stream-based candle closed events for the trade flow
    """

    def __init__(self, *, base_url: str, timeout_s: float = 30.0):
        """
        Initialize the signals HTTP client.

        Args:
            base_url: Base URL for api-signals.
            timeout_s: Total request timeout in seconds.
        """
        self._base_url = str(base_url).rstrip("/")
        self._timeout = httpx.Timeout(timeout_s, connect=5.0)
        self._client = httpx.AsyncClient(timeout=self._timeout)
        self._logger = logging.getLogger(self.__class__.__name__)

    async def aclose(self) -> None:
        """
        Close the underlying reusable HTTP client.
        """
        await self._client.aclose()

    async def candle_closed(
        self,
        *,
        indicator_set_id: str,
        ts: int,
        indicator_set: Optional[Dict[str, Any]] = None,
        indicator_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Notify api-signals that a candle closed for an indicator-driven flow.

        This is the existing LP-oriented trigger and is kept for backward compatibility.

        Args:
            indicator_set_id: Identifier of the indicator set.
            ts: Candle close timestamp in milliseconds.
            indicator_set: Optional serialized indicator set payload.
            indicator_snapshot: Optional serialized indicator snapshot payload.

        Returns:
            Parsed JSON response from api-signals.
        """
        payload: Dict[str, Any] = {
            "indicator_set_id": indicator_set_id,
            "ts": int(ts),
            "indicator_set": indicator_set,
            "indicator_snapshot": indicator_snapshot,
        }
        return await self._post_json("/api/triggers/candle-closed", payload)

    async def trade_candle_closed(
        self,
        *,
        stream_key: str,
        ts: int,
        source: str,
        symbol: str,
        interval: str,
        candle: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Notify api-signals that a candle closed for a stream-driven trade flow.

        This trigger is independent from indicator sets and allows api-signals
        to evaluate active trade strategies directly from a stream_key.

        Args:
            stream_key: Canonical stream identifier.
            ts: Candle close timestamp in milliseconds.
            source: Source label, such as binance.
            symbol: Trading symbol, such as BTCUSDT.
            interval: Candle interval, currently 1m.
            candle: Optional serialized candle payload.

        Returns:
            Parsed JSON response from api-signals.
        """
        payload: Dict[str, Any] = {
            "stream_key": str(stream_key),
            "ts": int(ts),
            "source": str(source),
            "symbol": str(symbol),
            "interval": str(interval),
            "candle": candle,
        }
        return await self._post_json("/api/triggers/trade-candle-closed", payload)

    async def _post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a POST request with a JSON body and return the decoded response.

        Args:
            path: Relative path in api-signals.
            payload: JSON payload to send.

        Returns:
            Parsed JSON response body.
        """
        url = f"{self._base_url}{path}"

        try:
            response = await self._client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            self._logger.warning(
                "Signals HTTP request failed. url=%s err=%s",
                url,
                exc,
            )
            raise