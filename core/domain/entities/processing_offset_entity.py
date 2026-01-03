# core/domain/entities/processing_offset_entity.py
from __future__ import annotations

from core.domain.entities.base_entity import MongoEntity


class ProcessingOffsetEntity(MongoEntity):
    """
   Tracks per-stream ingestion offsets.

    `last_closed_open_time` is used to resume/backfill without duplicates.
    """

    stream_key: str
    last_closed_open_time: int
