"""Configuración centralizada del sistema de trading.

Carga settings desde archivos YAML y variables de entorno.
Las variables de entorno tienen prioridad sobre los archivos YAML.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


# Rutas base
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


def load_yaml_config(path: Path | None = None) -> dict[str, Any]:
    """Carga configuración desde archivo YAML."""
    if path is None:
        path = CONFIG_DIR / "settings.yml"
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


class DatabaseSettings(BaseSettings):
    """Configuración de base de datos."""

    url: str = Field(
        default="postgresql://trading:trading_secret@localhost:5432/trading_db",
        alias="DATABASE_URL",
    )
    pool_size: int = 10
    max_overflow: int = 20


class RedisSettings(BaseSettings):
    """Configuración de Redis."""

    url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")


class ExchangeSettings(BaseSettings):
    """Configuración del exchange."""

    api_key: str = Field(default="", alias="BINANCE_API_KEY")
    api_secret: str = Field(default="", alias="BINANCE_API_SECRET")
    testnet: bool = Field(default=True, alias="BINANCE_TESTNET")


class OllamaSettings(BaseSettings):
    """Configuración del LLM local."""

    host: str = Field(default="http://localhost:11434", alias="OLLAMA_HOST")
    model: str = Field(default="qwen2.5:14b", alias="OLLAMA_MODEL")
    fallback_model: str = "llama3.1:8b"
    temperature: float = 0.1
    max_tokens: int = 256


class RiskSettings(BaseSettings):
    """Configuración de gestión de riesgo."""

    max_risk_per_trade: float = Field(default=0.01, alias="MAX_RISK_PER_TRADE")
    max_position_size: float = Field(default=0.20, alias="MAX_POSITION_SIZE")
    max_daily_loss: float = Field(default=0.02, alias="MAX_DAILY_LOSS")
    max_drawdown: float = Field(default=0.10, alias="MAX_DRAWDOWN")
    max_leverage: float = Field(default=3.0, alias="MAX_LEVERAGE")
    max_open_positions: int = 3
    min_confidence: float = Field(default=0.65, alias="MIN_CONFIDENCE")


class TradingSettings(BaseSettings):
    """Configuración de trading."""

    symbol: str = Field(default="BTC/USDT", alias="TRADING_SYMBOL")
    timeframe: str = Field(default="15m", alias="TRADING_TIMEFRAME")
    mode: str = Field(default="paper", alias="TRADING_MODE")  # paper | live


class Settings:
    """Configuración global del sistema.

    Combina YAML config + variables de entorno.
    Las variables de entorno tienen prioridad.
    """

    def __init__(self) -> None:
        self.yaml_config = load_yaml_config()
        self.database = DatabaseSettings()
        self.redis = RedisSettings()
        self.exchange = ExchangeSettings()
        self.ollama = OllamaSettings()
        self.risk = RiskSettings()
        self.trading = TradingSettings()

    @property
    def log_level(self) -> str:
        return os.getenv("LOG_LEVEL", "INFO")

    @property
    def log_dir(self) -> Path:
        return Path(os.getenv("LOG_DIR", "/data/logs"))

    @property
    def mlflow_tracking_uri(self) -> str:
        return os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")


# Singleton global
settings = Settings()
