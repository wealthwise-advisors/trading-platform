"""
ExternalCSVProvider — load historical data from your own CSV files.

Supports the format exported by most data vendors and brokers:
    Datetime,Open,High,Low,Close,Volume
    2024-01-02 09:30:00,4746.25,4748.50,4745.00,4747.75,1200

File lookup order for symbol "ES", date range 2024-01-01 → 2024-06-30:
  1. {dir}/ES_FULL.csv          ← single file covering everything (preferred)
  2. {dir}/ES_FULL_2024.csv     ← year-specific file
  3. {dir}/FULL_ES.csv          ← alternate naming (equities style)
  4. Multi-year: concatenates ES_FULL_2024.csv + ES_FULL_2025.csv etc.

Input data is expected to be 1-minute bars.  Any coarser timeframe is produced
by resampling (OHLCV aggregation) on the fly — no pre-processing needed.

Configure the data directory once in config/settings.yaml:
    data:
      external_dir: "C:/Data"

Or override per-call:  ExternalCSVProvider(data_dir="C:/Data")
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

import pandas as pd
from loguru import logger

from .base_provider import DataProvider, Bar
from ..config import resolve_config_dir


# Resample rules: pandas OHLCV aggregation
_OHLCV_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}

# Maps timeframe string → pandas offset alias
_TF_ALIAS = {
    "1m": "1min", "3m": "3min", "5m": "5min", "8m": "8min",
    "10m": "10min", "15m": "15min", "20m": "20min", "30m": "30min",
    "1h": "1h", "2h": "2h", "4h": "4h", "1d": "1D",
}


class ExternalCSVProvider(DataProvider):
    """
    Load OHLCV data from your own CSV files in any local directory.

    Args:
        data_dir: Directory containing the CSV files (e.g. "C:/Data").
                  Falls back to settings.yaml → data.external_dir if not given.
    """

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            data_dir = self._dir_from_config()
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
            raise FileNotFoundError(
                f"External data directory not found: {self.data_dir}\n"
                "Set it in config/settings.yaml under data.external_dir or "
                "pass data_dir= when constructing ExternalCSVProvider."
            )

    # ------------------------------------------------------------------
    # Config helper
    # ------------------------------------------------------------------

    @staticmethod
    def _dir_from_config() -> str:
        try:
            import yaml
            cfg_path = resolve_config_dir() / "settings.yaml"
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f)
            return cfg.get("data", {}).get("external_dir", "")
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # File discovery
    # ------------------------------------------------------------------

    def _find_file(self, symbol: str, year: Optional[int] = None) -> Optional[Path]:
        """Try common naming patterns and return the first match."""
        candidates = []
        if year:
            candidates += [
                f"{symbol}_FULL_{year}.csv",
                f"{symbol}_{year}.csv",
                f"FULL_{symbol}_{year}.csv",
            ]
        candidates += [
            f"{symbol}_FULL.csv",
            f"FULL_{symbol}.csv",
            f"{symbol}.csv",
        ]
        for name in candidates:
            p = self.data_dir / name
            if p.exists():
                return p
        return None

    def _collect_files(self, symbol: str, start: datetime, end: datetime) -> list[Path]:
        """
        Return the smallest set of files that covers [start, end].
        Prefers year-specific files (smaller) over the monolithic FULL file.
        """
        # 1. Try per-year files first — much smaller than the combined file
        years = list(range(start.year, end.year + 1))
        year_files = [p for yr in years for p in [self._find_file(symbol, yr)] if p]
        if len(year_files) == len(years):
            return year_files  # all years covered by smaller files

        # 2. Fall back to the single all-years file
        full_file = self._find_file(symbol)
        if full_file:
            return [full_file]

        # 3. Use whatever year files we found (partial coverage is better than nothing)
        if year_files:
            return year_files

        raise FileNotFoundError(
            f"No CSV file found for '{symbol}' in {self.data_dir}\n"
            f"Expected one of: {symbol}_FULL.csv, {symbol}_FULL_<year>.csv, FULL_{symbol}.csv\n"
            f"Files present: {[f.name for f in self.data_dir.glob('*.csv')]}"
        )

    # ------------------------------------------------------------------
    # Core load
    # ------------------------------------------------------------------

    def load(self, symbol: str, start: datetime, end: datetime, timeframe: str = "1m") -> pd.DataFrame:
        files = self._collect_files(symbol, start, end)
        logger.info(f"Loading {symbol} from {[f.name for f in files]}")

        frames = []
        for f in files:
            df = self._read_file_ranged(f, start, end)
            if not df.empty:
                frames.append(df)

        if not frames:
            raise ValueError(
                f"No bars found for {symbol} between {start} and {end} "
                f"in {[f.name for f in files]}"
            )

        df = pd.concat(frames).sort_index()
        df = df[~df.index.duplicated(keep="first")]
        df = df.loc[start:end]

        # Resample if not 1-minute
        if timeframe != "1m":
            df = self._resample(df, timeframe)

        logger.info(f"  {len(df)} {timeframe} bars  ({df.index.min()} → {df.index.max()})")
        return df

    # ------------------------------------------------------------------
    # File reading — chunked so we skip rows outside [start, end]
    # ------------------------------------------------------------------

    def _read_file_ranged(self, path: Path, start: datetime, end: datetime) -> pd.DataFrame:
        # Peek at headers to find the datetime column name
        header = pd.read_csv(path, nrows=0)
        dt_col = header.columns[0]
        float_cols = {c: "float32" for c in header.columns[1:]}

        chunks_kept: list[pd.DataFrame] = []
        # Read 50k rows at a time — enough for ~35 days of 1-minute bars per chunk
        reader = pd.read_csv(
            path,
            parse_dates=[dt_col],
            index_col=dt_col,
            dtype=float_cols,
            chunksize=50_000,
        )
        for chunk in reader:
            chunk.columns = chunk.columns.str.strip().str.lower()
            chunk.index.name = "timestamp"
            chunk.index = pd.to_datetime(chunk.index).tz_localize(None)

            chunk_end = chunk.index.max()
            chunk_start = chunk.index.min()

            # Skip chunks entirely before the start date
            if chunk_end < start:
                continue

            # Stop reading once the chunk is entirely past the end date
            if chunk_start > end:
                break

            # Keep only the rows inside [start, end] using a boolean mask
            # (avoids KeyError when the chunk index is not monotonic)
            sliced = chunk[(chunk.index >= start) & (chunk.index <= end)]
            if not sliced.empty:
                needed = {"open", "high", "low", "close", "volume"}
                missing = needed - set(sliced.columns)
                if missing:
                    raise ValueError(f"{path.name} is missing columns: {missing}")
                chunks_kept.append(sliced[["open", "high", "low", "close", "volume"]])

        return pd.concat(chunks_kept) if chunks_kept else pd.DataFrame()

    # ------------------------------------------------------------------
    # Resampling
    # ------------------------------------------------------------------

    def _resample(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        alias = _TF_ALIAS.get(timeframe)
        if alias is None:
            raise ValueError(
                f"Unknown timeframe '{timeframe}'. "
                f"Supported: {list(_TF_ALIAS.keys())}"
            )
        resampled = df.resample(alias).agg(_OHLCV_AGG).dropna()
        return resampled

    # ------------------------------------------------------------------
    # Streaming (not supported for CSV)
    # ------------------------------------------------------------------

    def stream(self, symbol: str, timeframe: str = "1m") -> Iterator[Bar]:
        raise NotImplementedError("ExternalCSVProvider does not support live streaming.")

    # ------------------------------------------------------------------
    # Convenience: list what's available
    # ------------------------------------------------------------------

    def list_available(self) -> list[str]:
        """Return the unique symbols found in data_dir."""
        symbols = set()
        for f in self.data_dir.glob("*.csv"):
            name = f.stem.upper()
            # Strip common suffixes: _FULL, _FULL_2024, _2024
            name = re.sub(r"_FULL(_\d{4})?$", "", name)
            name = re.sub(r"_\d{4}$", "", name)
            name = re.sub(r"^FULL_", "", name)
            symbols.add(name)
        return sorted(symbols)
