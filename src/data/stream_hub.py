"""One server-side Schwab stream for every chart (upgrade plan, Feature 3).

Before this, every live chart asked Schwab's REST API for its bars every 15 seconds.
Now one websocket per server subscribes CHART_FUTURES (finished 1-minute bars) and
LEVELONE_FUTURES (quotes, which build the minute still forming), keeps today's
1-minute bars in memory, and /live-refresh builds any intraday timeframe from them
with no call to Schwab. Whenever the hub cannot vouch for its bars -- not connected,
silent for 30 s, dropped since it was seeded, or asked for a time before its seed --
bars_1m() returns None and the caller fetches over REST exactly as before.

    hub.watch("ES")              start streaming ES (connects on first use)
    hub.bars_1m("ES", since)     1-minute bars from `since`, or None

Message parsing is a pure function of the messages (on_message), so the tests drive
it with Schwab's own envelopes and no network.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from src.data.schwab_provider import _FUTURES_ROOTS

log = logging.getLogger(__name__)
_ET = ZoneInfo("America/New_York")
_COLS = ["open", "high", "low", "close", "volume"]

#: Older than this and the hub is not trusted; Schwab sends a heartbeat every 10 s.
STALE_AFTER = timedelta(seconds=30)
CHART_FIELDS = "0,1,2,3,4,5,6"
QUOTE_FIELDS = "0,3,8,11"            # key, last price, total volume, trade time


def _et_minute(epoch_ms) -> datetime:
    t = datetime.fromtimestamp(int(epoch_ms) / 1000, tz=timezone.utc).astimezone(_ET)
    return t.replace(tzinfo=None, second=0, microsecond=0)


class StreamHub:
    def __init__(self, now=lambda: datetime.now(timezone.utc)):
        self._now = now
        self._lock = threading.Lock()
        self.connected = False
        self.error: str | None = None
        self._last_message: datetime | None = None
        self._bars: dict[str, dict[datetime, list[float]]] = {}
        self._covered_from: dict[str, datetime] = {}
        self._forming: dict[str, tuple[datetime, list[float], float]] = {}   # minute, bar, volume base
        self._quote: dict[str, dict] = {}                                      # last known fields
        self._roots: set[str] = set()
        self._thread: threading.Thread | None = None
        self._wake = threading.Event()

    # ── state, driven by messages ────────────────────────────────────────────

    def _root(self, key: str) -> str:
        k = str(key).lstrip("/").upper()
        if k not in self._roots and k[:-3] in self._roots:     # "/ESZ26" -> "ES"
            return k[:-3]
        return k

    def on_message(self, raw) -> None:
        try:
            msg = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        except ValueError:
            return
        if not isinstance(msg, dict):
            return
        with self._lock:
            self._last_message = self._now()
            for d in msg.get("data") or []:
                for c in d.get("content") or []:
                    try:
                        if d.get("service") == "CHART_FUTURES":
                            self._on_chart(c)
                        elif d.get("service") == "LEVELONE_FUTURES":
                            self._on_quote(c)
                    except (KeyError, TypeError, ValueError):
                        continue                         # a field missing or not a number

    def _on_chart(self, c: dict) -> None:
        root = self._root(c["key"])
        minute = _et_minute(c["1"])
        self._bars.setdefault(root, {})[minute] = [float(c[k]) for k in ("2", "3", "4", "5", "6")]
        f = self._forming.get(root)
        if f and f[0] <= minute:
            self._forming.pop(root)

    def _on_quote(self, c: dict) -> None:
        root = self._root(c["key"])
        q = self._quote.setdefault(root, {})
        prev_total = q.get("8")
        for k in ("3", "8", "11"):
            if k in c:
                q[k] = float(c[k])
        if "3" not in q or "11" not in q:
            return
        minute = _et_minute(q["11"])
        if minute in self._bars.get(root, {}):
            return                                       # that minute's real bar is in
        last, total = q["3"], q.get("8", 0.0)
        f = self._forming.get(root)
        if f is None or f[0] != minute:
            base = prev_total if prev_total is not None and prev_total <= total else total
            f = (minute, [last, last, last, last, 0.0], base)
        bar, base = f[1], f[2]
        if total < base:                                 # the day's volume restarted
            base = 0.0
        bar[1], bar[2], bar[3] = max(bar[1], last), min(bar[2], last), last
        bar[4] = total - base
        self._forming[root] = (minute, bar, base)

    def seed(self, root: str, df: pd.DataFrame) -> None:
        """Today's 1-minute bars from REST: what the stream builds on."""
        with self._lock:
            self._roots.add(root)
            bars = self._bars.setdefault(root, {})
            for ts, row in df[_COLS].iterrows():
                bars.setdefault(ts.to_pydatetime(), [float(v) for v in row])
            start = df.index.min().to_pydatetime() if len(df) else _et_minute(self._now().timestamp() * 1000)
            self._covered_from[root] = start

    def disconnected(self, why: str) -> None:
        """Bars may be missing from the drop: trust nothing until seeded again."""
        with self._lock:
            self.connected = False
            self.error = why
            self._covered_from.clear()
            self._forming.clear()

    def bars_1m(self, root: str, since: datetime) -> pd.DataFrame | None:
        root = root.upper()
        with self._lock:
            healthy = (self.connected and self._last_message is not None
                       and self._now() - self._last_message <= STALE_AFTER)
            start = self._covered_from.get(root)
            if not healthy or start is None or since < start:
                return None
            rows = dict(self._bars.get(root, {}))
            f = self._forming.get(root)
            if f and (not rows or f[0] > max(rows)):
                rows[f[0]] = list(f[1])
        rows = {t: v for t, v in rows.items() if t >= since}
        idx = pd.DatetimeIndex(sorted(rows), name="timestamp")
        return pd.DataFrame([rows[t] for t in idx], index=idx, columns=_COLS, dtype=float)

    # ── the connection ───────────────────────────────────────────────────────

    def watch(self, root: str) -> None:
        """Stream this root from now on. Starts the connection on first use; off when
        AUTOTRADER_STREAM=0 (the test suite), so nothing ever dials Schwab by accident."""
        root = root.upper().lstrip("/")
        if os.environ.get("AUTOTRADER_STREAM", "1") == "0" or root not in _FUTURES_ROOTS:
            return                                       # a stock keeps polling over REST
        with self._lock:
            new = root not in self._roots
            self._roots.add(root)
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, name="schwab-stream", daemon=True)
            self._thread.start()
        elif new:
            self._wake.set()

    def _run(self) -> None:
        backoff = 1
        while True:
            try:
                asyncio.run(self._session())
                backoff = 1
            except Exception as exc:                      # token, network, Schwab refusing
                log.warning("Schwab stream: %s", exc)
                self.disconnected(str(exc))
            threading.Event().wait(backoff)
            backoff = min(backoff * 2, 60)

    async def _session(self) -> None:
        import websockets
        from src.data.schwab_provider import SchwabDataProvider   # its client and its REST loader

        provider = SchwabDataProvider()
        provider._ensure_client()
        client = provider._client
        prefs = client.preferences()
        prefs.raise_for_status()
        info = prefs.json()["streamerInfo"][0]
        rid = 0

        def req(service, command, parameters=None):
            nonlocal rid
            rid += 1
            r = {"service": service, "command": command, "requestid": rid,
                 "SchwabClientCustomerId": info["schwabClientCustomerId"],
                 "SchwabClientCorrelId": info["schwabClientCorrelId"]}
            if parameters:
                r["parameters"] = parameters
            return r

        async with websockets.connect(info["streamerSocketUrl"], ping_interval=None) as ws:
            await ws.send(json.dumps({"requests": [req("ADMIN", "LOGIN", {
                "Authorization": client.access_token,
                "SchwabClientChannel": info["schwabClientChannel"],
                "SchwabClientFunctionId": info["schwabClientFunctionId"]})]}))
            login = json.loads(await asyncio.wait_for(ws.recv(), 20))
            code = login["response"][0]["content"]["code"]
            if code != 0:
                raise RuntimeError(f"login refused: {login['response'][0]['content'].get('msg')}")
            self.connected, self.error, self._last_message = True, None, self._now()
            log.info("Schwab stream connected")
            subscribed: set[str] = set()
            while True:
                with self._lock:
                    todo = sorted(self._roots - subscribed)
                if todo:
                    keys = ",".join(f"/{r}" for r in todo)
                    cmd = "ADD" if subscribed else "SUBS"
                    await ws.send(json.dumps({"requests": [
                        req("CHART_FUTURES", cmd, {"keys": keys, "fields": CHART_FIELDS}),
                        req("LEVELONE_FUTURES", cmd, {"keys": keys, "fields": QUOTE_FIELDS})]}))
                    for r in todo:                         # subscribed first, so no minute falls between
                        self.seed(r, await asyncio.to_thread(_seed_bars, provider, r))
                    subscribed |= set(todo)
                    self._wake.clear()
                try:
                    self.on_message(await asyncio.wait_for(ws.recv(), 2))
                except asyncio.TimeoutError:
                    if self._last_message and self._now() - self._last_message > STALE_AFTER:
                        raise RuntimeError("no message from Schwab for 30 s")


#: How far back a symbol is seeded. Four days: a 4h chart's newest bar can still be
#: Friday's when the Sunday-evening session opens, and the hub must cover it.
SEED_DAYS = 4


def _seed_bars(provider, root: str) -> pd.DataFrame:
    now_et = datetime.now(_ET).replace(tzinfo=None)
    try:
        return provider.load(root, now_et - timedelta(days=SEED_DAYS), now_et, "1m")
    except ValueError:
        # Nothing printed in the window (a long holiday): the stream starts the record.
        # Not an error -- raising here made the hub log in again every few seconds.
        return pd.DataFrame(columns=_COLS, index=pd.DatetimeIndex([], name="timestamp"), dtype=float)


#: The one hub the API uses.
hub = StreamHub()
