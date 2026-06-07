"""
RithmicDataProvider — downloads historical OHLCV bars via the Rithmic History API.

Setup (one-time, per developer):
  1. pip install -r requirements.txt
  2. Copy config/credentials.yaml.example → config/credentials.yaml
  3. Set rithmic.credentials_path to the directory containing your RITHMIC_LIVE.ini

  OR set the environment variable:
      RITHMIC_CREDENTIALS_PATH=/path/to/your/rithmic/credentials

  OR add to a .env file in the project root:
      RITHMIC_CREDENTIALS_PATH=/path/to/your/rithmic/credentials
"""

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Iterator

import pandas as pd
from dotenv import load_dotenv
from loguru import logger

from .base_provider import DataProvider, Bar

# Load .env file if present (useful for local dev without setting system env vars)
load_dotenv()

# Exchange codes for each root symbol
EXCHANGE_MAP: dict[str, str] = {
    "ES": "CME",  "MES": "CME",  "NQ": "CME",  "MNQ": "CME",
    "RTY": "CME", "MRY": "CME",  "YM": "CBOT", "MYM": "CBOT",
    "CL": "NYMEX","MCL": "NYMEX","NG": "NYMEX",
    "GC": "COMEX","MGC": "COMEX","SI": "COMEX",
    "ZN": "CBOT", "ZB": "CBOT",  "ZF": "CBOT",
}

# Rithmic-native bar periods (minutes)
_NATIVE_PERIODS = {1, 3, 5, 8, 10, 15, 20, 30}

# Module-level singletons — kept alive across Streamlit reruns in the same process
_order_api = None
_history_api = None

_SETUP_HELP = """
Rithmic credentials not configured. Pick one of these options:

  Option A — environment variable (recommended for CI/CD):
      set RITHMIC_CREDENTIALS_PATH=C:/path/to/credentials

  Option B — .env file in the project root:
      RITHMIC_CREDENTIALS_PATH=C:/path/to/credentials

  Option C — config/credentials.yaml:
      rithmic:
        credentials_path: C:/path/to/credentials

The credentials directory must contain a RITHMIC_LIVE.ini file.
See config/credentials.yaml.example for a full template.
"""


def _resolve_credentials_dir(override: str = None) -> str:
    """
    Resolve credentials directory from (in priority order):
      1. explicit override passed to RithmicDataProvider()
      2. RITHMIC_CREDENTIALS_PATH env var / .env file
      3. rithmic.credentials_path in config/credentials.yaml
    Raises a clear error if none is configured.
    """
    if override:
        return override

    # Env var (also picks up .env via load_dotenv above)
    env_path = os.environ.get("RITHMIC_CREDENTIALS_PATH", "").strip()
    if env_path:
        return env_path

    # config/credentials.yaml
    try:
        import yaml
        creds_file = Path("config/credentials.yaml")
        if creds_file.exists():
            data = yaml.safe_load(creds_file.read_text()) or {}
            path = (data.get("rithmic") or {}).get("credentials_path", "").strip()
            if path:
                return path
    except Exception:
        pass

    raise EnvironmentError(_SETUP_HELP)


def _ensure_apis(credentials_dir: str) -> tuple:
    global _order_api, _history_api
    if _history_api is not None:
        return _order_api, _history_api

    os.environ["RITHMIC_CREDENTIALS_PATH"] = credentials_dir

    try:
        from rithmic import RithmicOrderApi, RithmicHistoryApi, RithmicEnvironment
    except ImportError as exc:
        raise ImportError(
            "pyrithmic package not found.\n"
            "Install it with:  pip install pyrithmic\n"
            "or:               pip install -r requirements.txt"
        ) from exc

    logger.info(f"Connecting to Rithmic (credentials: {credentials_dir})")
    # Attempt standalone History API — sufficient for data downloads, no order perms needed.
    # Fall back to shared-loop pattern if the standalone init fails.
    try:
        _history_api = RithmicHistoryApi(env=RithmicEnvironment.RITHMIC_LIVE)
        logger.info("Rithmic History API connected")
    except Exception:
        logger.warning("Standalone History API failed — retrying with shared Order API loop")
        _order_api = RithmicOrderApi(env=RithmicEnvironment.RITHMIC_LIVE)
        _history_api = RithmicHistoryApi(
            env=RithmicEnvironment.RITHMIC_LIVE, loop=_order_api.loop
        )
        logger.info("Rithmic APIs connected (shared loop)")

    return _order_api, _history_api


def _timeframe_to_minutes(timeframe: str) -> int:
    tf = timeframe.strip().lower()
    if tf.endswith("h"):
        return int(tf[:-1]) * 60
    if tf.endswith("m"):
        return int(tf[:-1])
    raise ValueError(f"Cannot parse timeframe '{timeframe}'. Use e.g. '5m', '30m', '1h'.")


def _resample_ohlcv(df: pd.DataFrame, target_minutes: int) -> pd.DataFrame:
    rule = f"{target_minutes}min"
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    return df.resample(rule, closed="left", label="left").agg(agg).dropna(subset=["open"])


class RithmicDataProvider(DataProvider):
    """
    Downloads OHLCV bar data from Rithmic and caches it locally as CSV.

    Credentials are resolved automatically from env var / .env / credentials.yaml.
    Pass credentials_dir= explicitly to override.

    Example:
        provider = RithmicDataProvider()
        df = provider.load("ES", start_dt, end_dt, timeframe="5m")
    """

    def __init__(
        self,
        cache_dir: str = "data/historical",
        credentials_dir: str = None,
    ):
        self.cache_dir = Path(cache_dir)
        self._credentials_dir_override = credentials_dir  # None = auto-resolve

    def load(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "5m",
        exchange: str = None,
        use_cache: bool = True,
        force_download: bool = False,
    ) -> pd.DataFrame:
        """
        Return OHLCV DataFrame with DatetimeIndex for symbol over [start, end].

        symbol    : Root contract e.g. "ES", "NQ", "CL"
        timeframe : "1m" "3m" "5m" "8m" "10m" "15m" "20m" "30m" "1h"
        exchange  : Override auto-detected exchange (CME / NYMEX / COMEX / CBOT)
        use_cache : Skip download if cached CSV covers the requested range
        """
        minutes = _timeframe_to_minutes(timeframe)
        exchange = exchange or EXCHANGE_MAP.get(symbol.upper(), "CME")
        cache_path = self.cache_dir / f"{symbol}_{timeframe}.csv"

        if not force_download and use_cache and cache_path.exists():
            cached = self._load_cache(cache_path, start, end)
            if cached is not None:
                logger.info(f"Loaded {len(cached)} bars from cache: {cache_path}")
                return cached

        credentials_dir = _resolve_credentials_dir(self._credentials_dir_override)
        df = self._download(symbol, exchange, start, end, minutes, timeframe, credentials_dir)
        self._save_cache(df, cache_path)
        return df

    def stream(self, symbol: str, timeframe: str = "1m") -> Iterator[Bar]:
        raise NotImplementedError(
            "RithmicDataProvider is for historical data only. "
            "Live streaming is handled by RithmicBroker."
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _download(self, symbol, exchange, start, end, minutes, timeframe, credentials_dir):
        # Map to a native Rithmic period; resample if needed
        if minutes in _NATIVE_PERIODS:
            dl_minutes, resample = minutes, False
        else:
            candidates = sorted([p for p in _NATIVE_PERIODS if minutes % p == 0], reverse=True)
            dl_minutes = candidates[0] if candidates else 1
            resample = True

        logger.info(
            f"Downloading {symbol} {dl_minutes}m bars "
            f"[{start:%Y-%m-%d %H:%M} → {end:%Y-%m-%d %H:%M}]"
        )

        _, history_api = _ensure_apis(credentials_dir)
        download = history_api.download_historical_tick_data(
            symbol, exchange, start, end, dl_minutes
        )
        while not history_api.downloads_are_complete:
            time.sleep(0.05)

        df = download.tick_dataframe
        if df is None or df.empty:
            raise ValueError(
                f"Rithmic returned no data for {symbol} "
                f"[{start:%Y-%m-%d} → {end:%Y-%m-%d}]. "
                "Verify the symbol, exchange, and that the market was open."
            )

        df = self._normalize(df)
        if resample:
            df = _resample_ohlcv(df, minutes)

        logger.info(f"Downloaded {len(df)} bars for {symbol} ({timeframe})")
        return df

    def _normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        if not isinstance(df.index, pd.DatetimeIndex):
            if "timestamp" in df.columns:
                df = df.set_index("timestamp")
            df.index = pd.to_datetime(df.index)
        return df.sort_index()[["open", "high", "low", "close", "volume"]].dropna(subset=["open"])

    def _load_cache(self, path: Path, start: datetime, end: datetime) -> pd.DataFrame | None:
        try:
            df = pd.read_csv(path, parse_dates=["timestamp"], index_col="timestamp")
            df.columns = df.columns.str.lower()
            df = df.sort_index()
            if df.index.min() > pd.Timestamp(start) or df.index.max() < pd.Timestamp(end):
                return None
            return df.loc[pd.Timestamp(start):pd.Timestamp(end)]
        except Exception as exc:
            logger.warning(f"Cache read failed ({path}): {exc}")
            return None

    def _save_cache(self, df: pd.DataFrame, path: Path) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index_label="timestamp")
        logger.info(f"Cached {len(df)} bars → {path}")
