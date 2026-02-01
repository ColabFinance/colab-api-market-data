from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, getcontext
from typing import Optional, Set

from adapters.external.thegraph.pancakeswap_v3_base_pool_client import PancakeSwapV3BasePoolClient
from config.settings import settings
from core.domain.entities.token_registry_entity import TokenRegistryEntity
from core.repositories.system_config_repository import SystemConfigRepository
from core.repositories.token_registry_repository import TokenRegistryRepository


# high precision for sqrtPrice math
getcontext().prec = 80

Q192 = Decimal(2) ** Decimal(192)


def _norm_addr(v: str) -> str:
    return (v or "").strip().lower()


def _to_decimal(v: object, *, field: str) -> Decimal:
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"invalid_decimal_field:{field}")


def _to_int(v: object, *, field: str) -> int:
    try:
        return int(str(v))
    except (ValueError, TypeError):
        raise ValueError(f"invalid_int_field:{field}")


def _price_token1_per_token0_from_sqrt_price(
    *,
    sqrt_price_x96: int,
    decimals0: int,
    decimals1: int,
) -> Decimal:
    """
    Uniswap V3 math:
      price(token1/token0) = (sqrtPriceX96^2 / 2^192) * 10^(decimals0 - decimals1)
    """
    sp = Decimal(sqrt_price_x96)
    ratio = (sp * sp) / Q192
    scale = Decimal(10) ** Decimal(decimals0 - decimals1)
    return ratio * scale


@dataclass(frozen=True)
class TokenPriceResult:
    chain: str
    token_address: str
    price_usd: Decimal
    quote_token_address: str
    quote_token_is_usd_stable: bool
    price_in_quote: Decimal
    pool_address: str
    decimals: int

class TokenPricingUseCase:
    """
    Use case for:
    - Registering token pricing sources (pool-based) into Mongo
    - Resolving a token USD price on-demand via The Graph

    Key rule:
    - Do NOT trust token0Price/token1Price semantics from subgraphs.
      Prefer sqrtPriceX96 + decimals (deterministic).
    """

    def __init__(
        self,
        *,
        system_config_repo: SystemConfigRepository,
        token_registry_repo: TokenRegistryRepository,
    ) -> None:
        self._system_repo = system_config_repo
        self._token_repo = token_registry_repo

    async def register_from_pool(
        self,
        *,
        chain: str,
        dex: str,
        token_address: str,
        pool_address: str,
        subgraph_id: Optional[str] = None,
        quote_token_is_usd_stable: Optional[bool] = None,
    ) -> TokenRegistryEntity:
        runtime = await self._system_repo.get_runtime()
        api_key = ((runtime.thegraph_api_key if runtime else None) or "").strip()
        if not api_key:
            raise ValueError("thegraph_api_key_missing")

        chain = (chain or "base").strip().lower()

        # accept any label, but keep normalized
        dex = (dex or "pancakeswap_v3").strip().lower()
        if dex == "pancake_v3":
            dex = "pancakeswap_v3"

        token_address = _norm_addr(token_address)
        pool_address = _norm_addr(pool_address)

        tg = PancakeSwapV3BasePoolClient(api_key=api_key, subgraph_id=subgraph_id)
        try:
            data = await tg.get_pool(pool_address=pool_address)
        finally:
            await tg.aclose()

        token0 = (data.get("token0") or {}) if isinstance(data.get("token0"), dict) else {}
        token1 = (data.get("token1") or {}) if isinstance(data.get("token1"), dict) else {}

        token0_addr = _norm_addr(str(token0.get("id") or ""))
        token1_addr = _norm_addr(str(token1.get("id") or ""))

        if not token0_addr or not token1_addr:
            raise ValueError("pool_token_sides_missing")

        if token_address != token0_addr and token_address != token1_addr:
            raise ValueError("token_not_in_pool")

        token0_symbol = str(token0.get("symbol") or "") or None
        token1_symbol = str(token1.get("symbol") or "") or None

        token0_decimals = int(token0.get("decimals")) if token0.get("decimals") is not None else None
        token1_decimals = int(token1.get("decimals")) if token1.get("decimals") is not None else None

        if token0_decimals is None or token1_decimals is None:
            raise ValueError("pool_token_decimals_missing")

        # quote = other side of the pool
        if token_address == token0_addr:
            quote_addr = token1_addr
            quote_symbol = token1_symbol
        else:
            quote_addr = token0_addr
            quote_symbol = token0_symbol

        if quote_token_is_usd_stable is None:
            qs = (quote_symbol or "").upper()
            quote_token_is_usd_stable = qs in settings.USD_STABLE_SYMBOLS

        ent = TokenRegistryEntity(
            chain=chain,
            dex=dex,
            token_address=token_address,
            pool_address=pool_address,
            subgraph_id=(subgraph_id.strip() if subgraph_id else None),
            token0_address=token0_addr,
            token1_address=token1_addr,
            token0_symbol=token0_symbol,
            token1_symbol=token1_symbol,
            token0_decimals=token0_decimals,
            token1_decimals=token1_decimals,
            quote_token_address=quote_addr,
            quote_token_symbol=quote_symbol,
            quote_token_is_usd_stable=bool(quote_token_is_usd_stable),
        )

        await self._token_repo.upsert(ent)
        stored = await self._token_repo.get_by_token_address(chain=chain, token_address=token_address)
        return stored or ent

    async def get_token_usd_price(self, *, chain: str, token_address: str) -> TokenPriceResult:
        chain = (chain or "base").strip().lower()
        token_address = _norm_addr(token_address)

        ent = await self._token_repo.get_by_token_address(chain=chain, token_address=token_address)
        if not ent:
            raise LookupError("token_not_registered")

        visited: Set[str] = set()
        return await self._resolve_usd(chain=chain, ent=ent, visited=visited, depth=0)

    async def _resolve_usd(
        self,
        *,
        chain: str,
        ent: TokenRegistryEntity,
        visited: Set[str],
        depth: int,
    ) -> TokenPriceResult:
        if depth > 3:
            raise ValueError("quote_resolution_depth_exceeded")

        key = f"{chain}:{ent.token_address}"
        if key in visited:
            raise ValueError("quote_resolution_cycle")
        visited.add(key)

        runtime = await self._system_repo.get_runtime()
        api_key = ((runtime.thegraph_api_key if runtime else None) or "").strip()
        if not api_key:
            raise ValueError("thegraph_api_key_missing")

        tg = PancakeSwapV3BasePoolClient(api_key=api_key, subgraph_id=ent.subgraph_id)
        try:
            pool = await tg.get_pool(pool_address=ent.pool_address)
        finally:
            await tg.aclose()

        token0 = (pool.get("token0") or {}) if isinstance(pool.get("token0"), dict) else {}
        token1 = (pool.get("token1") or {}) if isinstance(pool.get("token1"), dict) else {}

        token0_addr = _norm_addr(str(token0.get("id") or ""))
        token1_addr = _norm_addr(str(token1.get("id") or ""))

        if not token0_addr or not token1_addr:
            raise ValueError("pool_token_sides_missing")

        decimals0 = ent.token0_decimals
        decimals1 = ent.token1_decimals
        if decimals0 is None or decimals1 is None:
            raise ValueError("registry_missing_decimals")

        if ent.token_address == token0_addr:
            token_decimals = int(decimals0)
        elif ent.token_address == token1_addr:
            token_decimals = int(decimals1)
        else:
            raise ValueError("token_not_in_pool")
        
        price_in_quote: Decimal | None = None

        sqrt_price_raw = pool.get("sqrtPrice")
        if sqrt_price_raw is not None:
            sqrt_price_x96 = _to_int(sqrt_price_raw, field="sqrtPrice")

            token1_per_token0 = _price_token1_per_token0_from_sqrt_price(
                sqrt_price_x96=sqrt_price_x96,
                decimals0=int(decimals0),
                decimals1=int(decimals1),
            )

            # price_in_quote = quote per 1 token(ent.token)
            # We know ent.quote_token_address is the "other side" of the pool.
            if ent.token_address == token0_addr and ent.quote_token_address == token1_addr:
                # token0 priced in token1
                price_in_quote = token1_per_token0
            elif ent.token_address == token1_addr and ent.quote_token_address == token0_addr:
                # token1 priced in token0
                if token1_per_token0 == 0:
                    raise ValueError("invalid_sqrt_price_ratio")
                price_in_quote = Decimal(1) / token1_per_token0
            else:
                # Registry / pool mismatch
                raise ValueError("token_not_in_pool")
        else:
            # Fallback (only if sqrtPrice missing)
            token0_price = pool.get("token0Price")
            token1_price = pool.get("token1Price")
            if token0_price is None and token1_price is None:
                raise ValueError("pool_prices_missing")

            # try to infer using registry quote direction:
            if ent.token_address == token0_addr and ent.quote_token_address == token1_addr:
                # we want quote(token1) per token0
                # depending on subgraph semantics, it might be token0Price OR 1/token1Price
                if token0_price is not None:
                    price_in_quote = _to_decimal(token0_price, field="token0Price")
                elif token1_price is not None:
                    v = _to_decimal(token1_price, field="token1Price")
                    price_in_quote = Decimal(1) / v
            elif ent.token_address == token1_addr and ent.quote_token_address == token0_addr:
                # we want quote(token0) per token1
                if token1_price is not None:
                    price_in_quote = _to_decimal(token1_price, field="token1Price")
                elif token0_price is not None:
                    v = _to_decimal(token0_price, field="token0Price")
                    price_in_quote = Decimal(1) / v
            else:
                raise ValueError("token_not_in_pool")

        if price_in_quote is None:
            raise ValueError("failed_to_compute_price_in_quote")

        # If quote token is USD-stable, USD price is direct
        if ent.quote_token_is_usd_stable:
            return TokenPriceResult(
                chain=chain,
                token_address=ent.token_address,
                price_usd=price_in_quote,
                quote_token_address=ent.quote_token_address,
                quote_token_is_usd_stable=True,
                price_in_quote=price_in_quote,
                pool_address=ent.pool_address,
                decimals=token_decimals,
            )

        # Otherwise resolve quote token USD recursively
        quote_ent = await self._token_repo.get_by_token_address(chain=chain, token_address=ent.quote_token_address)
        if not quote_ent:
            raise LookupError("quote_token_not_registered")

        quote_res = await self._resolve_usd(chain=chain, ent=quote_ent, visited=visited, depth=depth + 1)
        price_usd = price_in_quote * quote_res.price_usd

        return TokenPriceResult(
            chain=chain,
            token_address=ent.token_address,
            price_usd=price_usd,
            quote_token_address=ent.quote_token_address,
            quote_token_is_usd_stable=False,
            price_in_quote=price_in_quote,
            pool_address=ent.pool_address,
            decimals=token_decimals,
        )
