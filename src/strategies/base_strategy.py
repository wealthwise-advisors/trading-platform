from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
import pandas as pd

from ..data.base_provider import Bar


class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    CLOSE = "CLOSE"


@dataclass
class Signal:
    signal_type: SignalType
    strategy_name: str
    timestamp: datetime
    price: float
    reason: str = ""


class BaseStrategy(ABC):
    """
    All trading strategies inherit from this.

    Implement on_bar() to return a Signal or None each bar.
    The engine passes:
      - bars_df: full OHLCV DataFrame up to (and including) current bar
      - current_bar: the Bar object for this tick
      - position: current net position in contracts
    """

    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__

    def reset(self):
        """Called at the start of each backtest run. Override to reset state."""

    @abstractmethod
    def on_bar(self, bars_df: pd.DataFrame, current_bar: Bar, position: int) -> Optional[Signal]:
        """Return a Signal or None."""
