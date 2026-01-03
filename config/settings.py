# config/settings.py
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
   Application settings loaded from environment variables.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    LOG_LEVEL: str = Field(default="INFO")

    MONGODB_URL: str = Field(default="mongodb://mongo:27017")
    MONGODB_DB_NAME: str = Field(default="market_data")

    # Ingestion source name (future-proof for thegraph, etc.)
    INGESTION_SOURCE: str = Field(default="binance")

    # Binance configuration
    BINANCE_REST_BASE_URL: str = Field(default="https://api.binance.com")
    BINANCE_WS_BASE_URL: str = Field(default="wss://stream.binance.com:9443")

    BINANCE_STREAM_INTERVAL: str = Field(default="1m")
    BINANCE_STREAM_SYMBOLS: str = Field(default="btcusdt")

    ENABLE_BACKFILL_ON_START: bool = Field(default=True)


settings = Settings()
