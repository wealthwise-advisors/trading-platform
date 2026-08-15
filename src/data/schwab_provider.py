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
from .resample import bar_anchor, resample_ohlcv
from ..config import resolve_config_dir


_FUTURES_ROOTS = {
    "ES", "NQ", "MES", "MNQ", "RTY", "YM",
    "CL", "NG", "MCL", "RB", "HO",
    "GC", "SI", "MGC", "HG",
    "ZN", "ZB", "ZF", "ZT",
}

# How far back Schwab actually serves intraday bars.
#
# Measured 2026-08-11 by walking single-day probes backwards and bisecting the
# boundary, rather than taken from documentation:
#
#     /ES  5m   oldest data ~204 days back (2026-01-19), nothing by 205
#     /ES  1h   oldest data ~259 days back (2025-11-25), nothing by 261
#     AAPL 5m   oldest data ~208 days back (2026-01-15), nothing by 210
#
# Minute-based frequencies are the tighter constraint and the common case, so
# 180 is used: comfortably inside the measured ~204 so the boundary itself
# never gets advertised as available, and a round "about six months" to state
# to a user. Daily bars go back much further and are not covered by this.
#
# This is a moving window relative to today, not a fixed date -- which is why
# a request that worked last month can start failing without anything changing
# locally.
INTRADAY_LOOKBACK_DAYS = 180

# Maps timeframe string → (Schwab frequencyType, frequency)
_TF_MAP: dict[str, tuple[str, int]] = {
    "1m":  ("minute", 1),
    "5m":  ("minute", 5),
    "10m": ("minute", 10),
    "15m": ("minute", 15),
    "30m": ("minute", 30),
    "1h":  ("minute", 30),   # resampled client-side, like the intervals below
}

#: Minutes per timeframe label the app can ask for. Schwab serves only the
#: frequencies in _TF_MAP, so anything else is fetched at the largest frequency
#: that DIVIDES it and aggregated here. Resampling from a non-divisor would put
#: the wrong amount of market time in a bar -- a 45m bar built from 30m data
#: would hold 30 or 60 minutes -- so the divisor requirement is not optional.
_TF_MINUTES = {"1m": 1, "5m": 5, "10m": 10, "15m": 15, "20m": 20, "25m": 25,
               "30m": 30, "35m": 35, "40m": 40, "45m": 45, "1h": 60}
_NATIVE_MINUTES = {"1m": 1, "5m": 5, "10m": 10, "15m": 15, "30m": 30}


def _fetch_plan(timeframe: str):
    """(frequencyType, frequency, resample_alias_or_None) for a timeframe."""
    if timeframe in _TF_MAP and timeframe != "1h":
        return (*_TF_MAP[timeframe], None)
    if timeframe not in _TF_MINUTES:
        raise ValueError(
            f"Unsupported timeframe {timeframe!r}. Supported: {sorted(_TF_MINUTES)}"
        )
    want = _TF_MINUTES[timeframe]
    base = max((k for k, m in _NATIVE_MINUTES.items() if want % m == 0),
               key=lambda k: _NATIVE_MINUTES[k])
    return (*_TF_MAP[base], f"{want}min")

_OHLCV_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def build_timeframe(df: pd.DataFrame, timeframe: str, symbol: str | None = None) -> pd.DataFrame:
    """
    Turn natively-fetched bars into `timeframe` bars.

    A no-op for the frequencies Schwab serves directly (1/5/10/15/30m); the rest
    -- 20m, 25m, 35m, 40m, 45m, 1h -- are aggregated here on the session grid.

    Split out of load() so it is reachable without credentials or a network
    call. It was inline, which meant the only way to exercise it was against the
    live API, which meant in practice it was never exercised at all -- and it sat
    there resampling on a midnight grid through three rounds of "the bars are
    wrong" while the tests all passed against a separate copy of the logic.
    """
    _freq_type, _freq, resample_to = _fetch_plan(timeframe)
    if resample_to is None:
        return df
    return resample_ohlcv(df, timeframe, bar_anchor(symbol))


class SchwabDataProvider(DataProvider):
    """Fetch OHLCV bars from Schwab market data API (price_history endpoint)."""

    _REFRESH_TTL = 7 * 24 * 3600   # seconds
    _ACCESS_TTL  = 1800             # seconds
    _BASE_URL    = "https://api.schwabapi.com"

    def __init__(self, tokens_file: Optional[str] = None, session_start=None):
        #: Session open. Only used to anchor resample bins for the timeframes
        #: Schwab does not serve natively -- see load(). None keeps the
        #: calendar-day default, which is what a 24-hour chart wants.
        self.session_start = session_start
        creds = self._load_credentials()
        self._app_key      = creds["app_key"]
        self._app_secret   = creds["app_secret"]
        self._callback_url = creds.get("callback_url", "https://127.0.0.1")
        _default_tokens = str(resolve_config_dir() / "schwab_tokens.json")
        self._tokens_file = tokens_file or creds.get("tokens_file", _default_tokens)
        self._client = None   # lazily created after initial auth

    # ------------------------------------------------------------------
    # Credentials loading
    # ------------------------------------------------------------------

    @staticmethod
    def _load_credentials() -> dict:
        try:
            import yaml
            cfg_path = resolve_config_dir() / "credentials.yaml"
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

        freq_type, freq, resample_to = _fetch_plan(timeframe)
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
            oldest = datetime.datetime.now() - datetime.timedelta(days=INTRADAY_LOOKBACK_DAYS)
            hint = ""
            if start < oldest:
                hint = (
                    f"\nThat start date is {(datetime.datetime.now() - start).days} days back. "
                    f"Schwab serves roughly the last {INTRADAY_LOOKBACK_DAYS} days of intraday "
                    f"bars, i.e. nothing before about {oldest.date()}. "
                    "For older history use the CSV data source."
                )
            raise ValueError(
                f"No data returned from Schwab for {schwab_sym} "
                f"between {start} and {end}.{hint}"
                + ("" if hint else "\nCheck the symbol, date range, and that your "
                                   "account has data access.")
            )

        df = pd.concat(frames).sort_index()
        df = df[~df.index.duplicated(keep="first")]
        df = df.loc[start:end]

        # Anything Schwab does not serve natively is aggregated on the session
        # grid, the same way every other path in the app does it. This used to
        # be a bare df.resample() here, which anchors bins at MIDNIGHT, so all
        # six built timeframes started their session on the wrong minute
        # (09:30 session: 20m opened 09:40, 45m at 09:45, 1h at 10:00).
        df = build_timeframe(df, timeframe, symbol)

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
