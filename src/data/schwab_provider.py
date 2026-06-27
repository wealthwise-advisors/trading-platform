"""
SchwabDataProvider — historical OHLCV bars from Charles Schwab market data API.

Credentials in config/credentials.yaml (gitignored):
  schwab:
    app_key: "YOUR_32_CHAR_APP_KEY"
    app_secret: "YOUR_16_CHAR_SECRET"
    callback_url: "https://127.0.0.1"
    tokens_file: "config/schwab_tokens.json"

Authentication flow (first time or every 7 days):
  1. provider.get_auth_url()         → open in browser
  2. Approve → browser redirects to callback URL with ?code=...
  3. provider.complete_auth(url)     → exchanges code for tokens

After initial auth the access token (30 min) is auto-refreshed by a daemon
thread inside the schwabdev Client. The refresh token lives 7 days — the
Streamlit sidebar widget warns 24 h before expiry.
"""

from __future__ import annotations

import base64
import datetime
import json
from datetime import timezone
from pathlib import Path
from typing import Iterator, Optional, Tuple

import pandas as pd
import requests
from loguru import logger

from .base_provider import DataProvider, Bar


_FUTURES_ROOTS = {
    "ES", "NQ", "MES", "MNQ", "RTY", "YM",
    "CL", "NG", "MCL", "RB", "HO",
    "GC", "SI", "MGC", "HG",
    "ZN", "ZB", "ZF", "ZT",
}

# Maps timeframe string → (Schwab frequencyType, frequency)
_TF_MAP: dict[str, tuple[str, int]] = {
    "1m":  ("minute", 1),
    "5m":  ("minute", 5),
    "10m": ("minute", 10),
    "15m": ("minute", 15),
    "30m": ("minute", 30),
    "1h":  ("minute", 30),   # we resample 30m → 1h client-side
}

_OHLCV_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


class SchwabDataProvider(DataProvider):
    """Fetch OHLCV bars from Schwab market data API (price_history endpoint)."""

    _REFRESH_TTL = 7 * 24 * 3600   # seconds
    _ACCESS_TTL  = 1800             # seconds
    _BASE_URL    = "https://api.schwabapi.com"

    def __init__(self, tokens_file: Optional[str] = None):
        creds = self._load_credentials()
        self._app_key      = creds["app_key"]
        self._app_secret   = creds["app_secret"]
        self._callback_url = creds.get("callback_url", "https://127.0.0.1")
        _default_tokens = str(
            Path(__file__).parent.parent.parent / "config" / "schwab_tokens.json"
        )
        self._tokens_file = tokens_file or creds.get("tokens_file", _default_tokens)
        self._client = None   # lazily created after initial auth

    # ------------------------------------------------------------------
    # Credentials loading
    # ------------------------------------------------------------------

    @staticmethod
    def _load_credentials() -> dict:
        try:
            import yaml
            cfg_path = Path(__file__).parent.parent.parent / "config" / "credentials.yaml"
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f)
            schwab = cfg.get("schwab", {})
            if not schwab.get("app_key") or not schwab.get("app_secret"):
                raise ValueError(
                    "Schwab credentials missing in config/credentials.yaml.\n"
                    "Add a 'schwab:' section with app_key and app_secret.\n"
                    "See config/credentials.yaml.example for the template."
                )
            return schwab
        except FileNotFoundError:
            raise FileNotFoundError(
                "config/credentials.yaml not found.\n"
                "Copy config/credentials.yaml.example → config/credentials.yaml "
                "and fill in your Schwab app credentials."
            )

    # ------------------------------------------------------------------
    # Token file I/O
    # ------------------------------------------------------------------

    def _read_tokens(self) -> Tuple[Optional[datetime.datetime], Optional[datetime.datetime], Optional[dict]]:
        try:
            with open(self._tokens_file) as f:
                d = json.load(f)
            at = datetime.datetime.fromisoformat(d["access_token_issued"])
            rt = datetime.datetime.fromisoformat(d["refresh_token_issued"])
            return at, rt, d["token_dictionary"]
        except Exception:
            return None, None, None

    def _write_tokens(
        self,
        at_issued: datetime.datetime,
        rt_issued: datetime.datetime,
        token_dict: dict,
    ) -> None:
        Path(self._tokens_file).parent.mkdir(parents=True, exist_ok=True)
        with open(self._tokens_file, "w") as f:
            json.dump(
                {
                    "access_token_issued": at_issued.isoformat(),
                    "refresh_token_issued": rt_issued.isoformat(),
                    "token_dictionary": token_dict,
                },
                f,
                indent=4,
            )

    # ------------------------------------------------------------------
    # Auth status — exposed to the Streamlit widget
    # ------------------------------------------------------------------

    def is_authenticated(self) -> bool:
        """True if a tokens file exists with a non-expired refresh token."""
        _, rt_issued, td = self._read_tokens()
        if None in (rt_issued, td):
            return False
        age = (datetime.datetime.now(timezone.utc) - rt_issued).total_seconds()
        return age < self._REFRESH_TTL

    def refresh_token_hours_remaining(self) -> float:
        """Hours until the refresh token (7-day window) expires. 0 if expired."""
        _, rt_issued, td = self._read_tokens()
        if None in (rt_issued, td):
            return 0.0
        age = (datetime.datetime.now(timezone.utc) - rt_issued).total_seconds()
        return max(0.0, (self._REFRESH_TTL - age) / 3600)

    def needs_reauth(self) -> bool:
        """True when refresh token expires in < 24 hours."""
        return self.refresh_token_hours_remaining() < 24

    # ------------------------------------------------------------------
    # OAuth helpers (no webbrowser / no input() — UI handles interaction)
    # ------------------------------------------------------------------

    def _auth_header(self) -> str:
        return base64.b64encode(f"{self._app_key}:{self._app_secret}".encode()).decode()

    def _post_oauth_token(self, grant_type: str, code: str) -> requests.Response:
        headers = {
            "Authorization": f"Basic {self._auth_header()}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        if grant_type == "authorization_code":
            data = {"grant_type": "authorization_code", "code": code, "redirect_uri": self._callback_url}
        else:
            data = {"grant_type": "refresh_token", "refresh_token": code}
        return requests.post(f"{self._BASE_URL}/v1/oauth/token", headers=headers, data=data, timeout=15)

    def get_auth_url(self) -> str:
        """Return the Schwab OAuth2 authorization URL (open in browser)."""
        return (
            f"{self._BASE_URL}/v1/oauth/authorize"
            f"?client_id={self._app_key}&redirect_uri={self._callback_url}"
        )

    def complete_auth(self, redirect_url: str) -> None:
        """
        Exchange the authorization code from the browser redirect URL for tokens.

        Call this after the user pastes the redirect URL from their browser.
        Writes schwab_tokens.json and resets the internal client so the next
        load() call creates a fresh authenticated Client.
        """
        try:
            code_start = redirect_url.index("code=") + 5
            code_end   = redirect_url.index("%40")
            code = redirect_url[code_start:code_end] + "@"
        except ValueError:
            raise ValueError(
                "Could not parse auth code from the URL.\n"
                "Make sure you copied the full address bar URL after authorization."
            )
        resp = self._post_oauth_token("authorization_code", code)
        if not resp.ok:
            raise RuntimeError(f"Schwab auth failed ({resp.status_code}): {resp.text}")
        now = datetime.datetime.now(timezone.utc)
        self._write_tokens(now, now, resp.json())
        self._client = None   # force re-creation with new tokens
        logger.info("Schwab tokens written — authentication complete.")

    # ------------------------------------------------------------------
    # Lazy client init (requires valid tokens)
    # ------------------------------------------------------------------

    def _ensure_client(self) -> None:
        if self._client is not None:
            return
        if not self.is_authenticated():
            raise RuntimeError(
                "Schwab tokens are missing or expired.\n"
                "Use the re-authenticate widget in the sidebar."
            )
        from .schwabdev import Client
        self._client = Client(
            self._app_key,
            self._app_secret,
            self._callback_url,
            self._tokens_file,
            update_tokens_auto=True,
            verbose=False,
        )

    # ------------------------------------------------------------------
    # Symbol mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _to_schwab_symbol(symbol: str) -> str:
        if symbol.startswith("/"):
            return symbol
        root = symbol.upper()
        if root in _FUTURES_ROOTS:
            return f"/{root}"
        return symbol

    # ------------------------------------------------------------------
    # DataProvider.load()
    # ------------------------------------------------------------------

    def load(
        self,
        symbol: str,
        start: datetime.datetime,
        end: datetime.datetime,
        timeframe: str = "1m",
    ) -> pd.DataFrame:
        self._ensure_client()

        if timeframe not in _TF_MAP:
            raise ValueError(
                f"Unsupported timeframe '{timeframe}'. Supported: {list(_TF_MAP)}"
            )
        freq_type, freq = _TF_MAP[timeframe]
        schwab_sym = self._to_schwab_symbol(symbol)
        logger.info(f"Schwab: {schwab_sym} {timeframe} bars {start.date()} → {end.date()}")

        # Chunk into 30-day windows (Schwab minute data limit ≈ 47 days)
        frames: list[pd.DataFrame] = []
        chunk_start = start
        while chunk_start < end:
            chunk_end = min(chunk_start + datetime.timedelta(days=30), end)
            chunk = self._fetch_chunk(schwab_sym, freq_type, freq, chunk_start, chunk_end)
            if not chunk.empty:
                frames.append(chunk)
            chunk_start = chunk_end + datetime.timedelta(seconds=1)

        if not frames:
            raise ValueError(
                f"No data returned from Schwab for {schwab_sym} "
                f"between {start} and {end}.\n"
                "Check the symbol, date range, and that your account has data access."
            )

        df = pd.concat(frames).sort_index()
        df = df[~df.index.duplicated(keep="first")]
        df = df.loc[start:end]

        if timeframe == "1h":
            df = df.resample("1h").agg(_OHLCV_AGG).dropna()

        logger.info(f"  {len(df)} {timeframe} bars  ({df.index.min()} → {df.index.max()})")
        return df

    def _fetch_chunk(
        self,
        symbol: str,
        freq_type: str,
        freq: int,
        start: datetime.datetime,
        end: datetime.datetime,
    ) -> pd.DataFrame:
        from zoneinfo import ZoneInfo
        _ET = ZoneInfo("America/New_York")
        # start/end are naive ET datetimes; localize as ET so dt.timestamp()
        # in schwabdev produces the correct UTC epoch regardless of machine timezone.
        start_et = start.replace(tzinfo=_ET)
        end_et   = end.replace(tzinfo=_ET)
        resp = self._client.price_history(
            symbol=symbol,
            frequencyType=freq_type,
            frequency=freq,
            startDate=start_et,
            endDate=end_et,
            needExtendedHoursData=True,
        )
        if not resp.ok:
            logger.warning(f"Schwab API {resp.status_code}: {resp.text[:200]}")
            return pd.DataFrame()

        data = resp.json()
        if data.get("empty", True) or not data.get("candles"):
            return pd.DataFrame()

        rows = []
        for c in data["candles"]:
            ts = (
                datetime.datetime.fromtimestamp(c["datetime"] / 1000, tz=timezone.utc)
                .astimezone(_ET)
                .replace(tzinfo=None)
            )
            rows.append({
                "timestamp": ts,
                "open":   float(c["open"]),
                "high":   float(c["high"]),
                "low":    float(c["low"]),
                "close":  float(c["close"]),
                "volume": float(c.get("volume", 0)),
            })

        return pd.DataFrame(rows).set_index("timestamp")

    # ------------------------------------------------------------------
    # Streaming — not yet implemented
    # ------------------------------------------------------------------

    def stream(self, symbol: str, timeframe: str = "1m") -> Iterator[Bar]:
        raise NotImplementedError("SchwabDataProvider.stream() is not yet implemented.")
