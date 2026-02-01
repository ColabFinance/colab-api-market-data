from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from adapters.external.database.system_config_repository_mongodb import SystemConfigRepositoryMongoDB
from adapters.external.database.token_registry_repository_mongodb import TokenRegistryRepositoryMongoDB
from core.usecases.token_pricing_use_case import TokenPricingUseCase

from .deps import get_db
from .dtos.token_registry_dtos import TokenPriceOutDTO


router = APIRouter(prefix="/pricing", tags=["pricing"])


def _uc(db: AsyncIOMotorDatabase) -> TokenPricingUseCase:
    return TokenPricingUseCase(
        system_config_repo=SystemConfigRepositoryMongoDB(db),
        token_registry_repo=TokenRegistryRepositoryMongoDB(db),
    )


@router.get("/tokens/{token_address}/usd", response_model=TokenPriceOutDTO)
async def get_token_price_usd(
    token_address: str,
    chain: str = "base",
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> TokenPriceOutDTO:
    """
    Returns the current USD price for a registered token.

    Flow:
    - checks Mongo token registry
    - queries The Graph for current pool spot price
    - resolves USD (direct if quote is stable; otherwise resolves quote token USD recursively)
    """
    uc = _uc(db)
    try:
        res = await uc.get_token_usd_price(chain=chain, token_address=token_address)
        return TokenPriceOutDTO(
            chain=res.chain,
            token_address=res.token_address,
            price_usd=str(res.price_usd),
            quote_token_address=res.quote_token_address,
            quote_token_is_usd_stable=res.quote_token_is_usd_stable,
            price_in_quote=str(res.price_in_quote),
            pool_address=res.pool_address,
            decimals=int(res.decimals),
        )
    except LookupError as exc:
        msg = str(exc)
        if msg == "token_not_registered":
            raise HTTPException(status_code=404, detail=msg)
        if msg == "quote_token_not_registered":
            raise HTTPException(status_code=409, detail=msg)
        raise HTTPException(status_code=404, detail=msg)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"failed_to_resolve_price: {exc}")
