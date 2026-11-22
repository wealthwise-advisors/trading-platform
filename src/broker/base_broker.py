from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class Order:
    symbol: str
    side: OrderSide
    quantity: int                  # number of contracts
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    order_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: OrderStatus = OrderStatus.PENDING
    created_at: Optional[datetime] = None
    strategy_tag: str = ""         # which strategy generated this order
    #: A bracket leg: inactive until this order fills (and cancelled with it).
    parent_id: Optional[str] = None
    #: One fill in the group cancels the rest (a bracket's target and stop).
    oco_group: Optional[str] = None
    #: A trailing stop: after each bar the stop follows the best price by this many ticks.
    trail_ticks: Optional[int] = None
    #: A STOP_LIMIT whose stop has been reached; it now works as a limit order.
    triggered: bool = False


@dataclass
class Fill:
    order_id: str
    symbol: str
    side: OrderSide
    quantity: int
    fill_price: float
    commission: float
    filled_at: datetime
    strategy_tag: str = ""


class BaseBroker(ABC):
    @abstractmethod
    def submit_order(self, order: Order) -> str:
        """Submit an order. Returns order_id."""

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""

    @abstractmethod
    def get_position(self, symbol: str) -> int:
        """Return net position in contracts (+long, -short)."""

    @abstractmethod
    def get_cash(self) -> float:
        """Return available cash balance."""

    @abstractmethod
    def get_fills(self) -> list[Fill]:
        """Return all fills so far."""
