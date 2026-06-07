from datetime import datetime
from pathlib import Path
from typing import Iterator
import pandas as pd
from loguru import logger

from .base_provider import DataProvider, Bar


class CSVDataProvider(DataProvider):
    """Load OHLCV data from CSV files.

    Expected CSV columns: timestamp, open, high, low, close, volume
    Timestamp can be any format pandas can parse.
    """

    def __init__(self, data_dir: str = "data/historical"):
        self.data_dir = Path(data_dir)

    def load(self, symbol: str, start: datetime, end: datetime, timeframe: str = "1m") -> pd.DataFrame:
        path = self.data_dir / f"{symbol}_{timeframe}.csv"
        if not path.exists():
            raise FileNotFoundError(f"No data file found: {path}")

        df = pd.read_csv(path, parse_dates=["timestamp"], index_col="timestamp")
        df.columns = df.columns.str.lower()
        df = df.sort_index()
        df = df.loc[start:end]
        logger.debug(f"Loaded {len(df)} bars for {symbol} from {path}")
        return df

    def stream(self, symbol: str, timeframe: str = "1m") -> Iterator[Bar]:
        raise NotImplementedError("CSVDataProvider does not support live streaming. Use RithmicProvider.")

    def save(self, df: pd.DataFrame, symbol: str, timeframe: str = "1m") -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = self.data_dir / f"{symbol}_{timeframe}.csv"
        df.to_csv(path, index_label="timestamp")
        logger.info(f"Saved {len(df)} bars to {path}")
        return path
