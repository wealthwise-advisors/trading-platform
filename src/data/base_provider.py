from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator
import pandas as pd


@dataclass
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str = ""
    timeframe: str = "1m"

    @property
    def typical_price(self) -> float:
        return (self.high + self.low + self.close) / 3

    @property
    def mid(self) -> float:
        return (self.high + self.low) / 2


class DataProvider(ABC):
    """Abstract base for all data sources (CSV, Rithmic, yfinance, etc.)."""

    @abstractmethod
    def load(self, symbol: str, start: datetime, end: datetime, timeframe: str = "1m") -> pd.DataFrame:
        """Return OHLCV DataFrame with DatetimeIndex."""

    @abstractmethod
    def stream(self, symbol: str, timeframe: str = "1m") -> Iterator[Bar]:
        """Yield live bars (used in live trading)."""

    @staticmethod
    def df_to_bars(df: pd.DataFrame, symbol: str = "", timeframe: str = "1m") -> list[Bar]:
        bars = []
        for ts, row in df.iterrows():
            bars.append(Bar(
                timestamp=ts if isinstance(ts, datetime) else ts.to_pydatetime(),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("volume", 0)),
                symbol=symbol,
                timeframe=timeframe,
            ))
        return bars
