from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from adapters.external.database.candle_repository_mongodb import CandleRepositoryMongoDB
from adapters.external.database.indicator_repository_mongodb import IndicatorRepositoryMongoDB
from adapters.external.database.indicator_set_repository_mongodb import IndicatorSetRepositoryMongoDB
from core.usecases.market_data_use_case import MarketDataUseCase

from .deps import get_db
from .dtos.candle_dtos import CandleOutDTO
from .dtos.indicator_dtos import IndicatorSnapshotOutDTO
from .dtos.indicator_set_dtos import IndicatorSetCreateDTO, IndicatorSetOutDTO


router = APIRouter(prefix="/market-data", tags=["market-data"])


def get_use_case(db: AsyncIOMotorDatabase) -> MarketDataUseCase:
    return MarketDataUseCase(
        candle_repo=CandleRepositoryMongoDB(db),
        indicator_repo=IndicatorRepositoryMongoDB(db),
        indicator_set_repo=IndicatorSetRepositoryMongoDB(db),
    )


@router.post("/indicator-sets", response_model=IndicatorSetOutDTO)
async def create_indicator_set(
    dto: IndicatorSetCreateDTO,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> IndicatorSetOutDTO:
    """
    Create (or reuse) an ACTIVE indicator set.

    This endpoint is safe to call multiple times with the same params:
    it will always return the same cfg_hash.
    """
    try:
        uc = get_use_case(db)
        await uc.ensure_indexes()

        stored = await uc.upsert_active_indicator_set(
            symbol=dto.symbol,
            ema_fast=dto.ema_fast,
            ema_slow=dto.ema_slow,
            atr_window=dto.atr_window,
            source=dto.source,
            pool_address=dto.pool_address,
        )
        return IndicatorSetOutDTO.model_validate(stored.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create indicator set: {exc}") from exc


@router.get("/indicator-sets", response_model=List[IndicatorSetOutDTO])
async def list_indicator_sets(
    stream_key: Optional[str] = Query(None, description="Filter by stream_key"),
    status: Optional[str] = Query("ACTIVE"),
    limit: int = Query(5000, ge=1, le=5000),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> List[IndicatorSetOutDTO]:
    """
    List indicator sets with optional filters.
    """
    uc = get_use_case(db)
    await uc.ensure_indexes()

    items = await uc.list_indicator_sets(stream_key=stream_key, status=status, limit=int(limit))
    return [IndicatorSetOutDTO.model_validate(x.model_dump()) for x in items]


@router.get("/indicator-sets/{cfg_hash}", response_model=IndicatorSetOutDTO)
async def get_indicator_set(
    cfg_hash: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> IndicatorSetOutDTO:
    """
    Fetch a single indicator set by cfg_hash.
    """
    uc = get_use_case(db)
    await uc.ensure_indexes()

    ent = await uc.get_indicator_set(cfg_hash=cfg_hash)
    if not ent:
        raise HTTPException(status_code=404, detail="Indicator set not found.")
    return IndicatorSetOutDTO.model_validate(ent.model_dump())


@router.get("/candles", response_model=List[CandleOutDTO])
async def list_candles(
    stream_key: str = Query(..., description="e.g. binance:BTCUSDT:1m"),
    limit: int = Query(500, ge=1, le=5000),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> List[CandleOutDTO]:
    """
    List latest closed candles for a stream_key.
    """
    uc = get_use_case(db)
    await uc.ensure_indexes()

    candles = await uc.list_candles(stream_key=stream_key, limit=int(limit))
    return [CandleOutDTO.model_validate(c.model_dump()) for c in candles]


@router.get("/indicators", response_model=List[IndicatorSnapshotOutDTO])
async def list_indicators(
    stream_key: str = Query(..., description="e.g. binance:BTCUSDT:1m"),
    cfg_hash: Optional[str] = Query(None, description="Filter by indicator-set cfg_hash"),
    limit: int = Query(500, ge=1, le=5000),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> List[IndicatorSnapshotOutDTO]:
    """
    List latest indicator snapshots for a stream_key (optionally filtered by cfg_hash).
    """
    uc = get_use_case(db)
    await uc.ensure_indexes()

    snaps = await uc.list_indicators(stream_key=stream_key, cfg_hash=cfg_hash, limit=int(limit))
    return [IndicatorSnapshotOutDTO.model_validate(s.model_dump()) for s in snaps]
