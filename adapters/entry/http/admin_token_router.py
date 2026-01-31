from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from adapters.external.database.system_config_repository_mongodb import SystemConfigRepositoryMongoDB
from adapters.external.database.token_registry_repository_mongodb import TokenRegistryRepositoryMongoDB
from core.usecases.token_pricing_use_case import TokenPricingUseCase

from .deps import get_db
from .dtos.token_registry_dtos import TokenRegisterFromPoolDTO, TokenRegistryOutDTO


router = APIRouter(prefix="/admin/tokens", tags=["admin-tokens"])


def _uc(db: AsyncIOMotorDatabase) -> TokenPricingUseCase:
    return TokenPricingUseCase(
        system_config_repo=SystemConfigRepositoryMongoDB(db),
        token_registry_repo=TokenRegistryRepositoryMongoDB(db),
    )


@router.post("/register-from-pool", response_model=TokenRegistryOutDTO)
async def register_token_from_pool(
    dto: TokenRegisterFromPoolDTO,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> TokenRegistryOutDTO:
    """
    Register (or update) a token pricing source using a V3 pool.

    This stores everything needed in Mongo so the pricing endpoint can:
    - check if token is registered
    - fetch price on-demand via The Graph using only the stored data
    """
    uc = _uc(db)
    try:
        ent = await uc.register_from_pool(
            chain=dto.chain,
            dex=dto.dex,
            token_address=dto.token_address,
            pool_address=dto.pool_address,
            subgraph_id=dto.subgraph_id,
            quote_token_is_usd_stable=dto.quote_token_is_usd_stable,
        )
        return TokenRegistryOutDTO.model_validate(ent.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"failed_to_register_token: {exc}")


@router.get("/{token_address}", response_model=TokenRegistryOutDTO)
async def get_registered_token(
    token_address: str,
    chain: str = "base",
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> TokenRegistryOutDTO:
    uc = _uc(db)
    repo = TokenRegistryRepositoryMongoDB(db)

    ent = await repo.get_by_token_address(chain=chain.lower(), token_address=token_address.lower())
    if not ent:
        raise HTTPException(status_code=404, detail="token_not_registered")
    return TokenRegistryOutDTO.model_validate(ent.model_dump())


@router.get("", response_model=List[TokenRegistryOutDTO])
async def list_registered_tokens(
    chain: str = "base",
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> List[TokenRegistryOutDTO]:
    repo = TokenRegistryRepositoryMongoDB(db)
    items = await repo.list_all(chain=chain.lower())
    return [TokenRegistryOutDTO.model_validate(x.model_dump()) for x in items]
