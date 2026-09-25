"""Interfaz abstracta para brokers.

Define el contrato que deben implementar todos los brokers
(PaperBroker, BinanceBroker, etc.)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    """Representa una orden de trading."""

    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None  # None para market orders
    status: OrderStatus = OrderStatus.PENDING
    filled_price: Optional[float] = None
    filled_quantity: float = 0.0
    fee: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    filled_at: Optional[datetime] = None


@dataclass
class Position:
    """Representa una posición abierta."""

    symbol: str
    side: OrderSide
    quantity: float
    entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    leverage: float = 1.0


@dataclass
class Balance:
    """Representa el balance de la cuenta."""

    total: float
    available: float
    in_positions: float
    unrealized_pnl: float


class Broker(ABC):
    """Interfaz abstracta para brokers.

    Todos los brokers (paper, binance, etc.) deben implementar
    esta interfaz para que el sistema pueda cambiar de broker
    sin modificar la lógica de trading.
    """

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        price: float | None = None,
    ) -> Order:
        """Colocar una orden."""
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancelar una orden pendiente."""
        ...

    @abstractmethod
    async def get_position(self, symbol: str) -> Position | None:
        """Obtener posición actual para un símbolo."""
        ...

    @abstractmethod
    async def get_balance(self) -> Balance:
        """Obtener balance de la cuenta."""
        ...

    @abstractmethod
    async def get_open_orders(self, symbol: str | None = None) -> list[Order]:
        """Obtener órdenes abiertas."""
        ...
