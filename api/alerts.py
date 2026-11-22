"""Price alerts checked on the server (upgrade plan, Feature 4).

The alerts are the chart's own (the Alert button, lib/priceAlerts.ts). Since Phase 1 they
are kept in the account's settings document, so the server can read them without an
editor of its own. Every CHECK_EVERY seconds the checker prices the symbols that have
alerts -- from the Schwab stream when it is up, otherwise one REST quote request no more
than every 15 s -- and records each alert reached, once (alert_events is UNIQUE per
alert, so a restart cannot fire it again). The app asks for events it has not shown and
announces them, including ones that fired while no browser was open.

CONDITION ALERTS (check_conditions): a scan -- RSI / StochRSI / MFI levels and crossings,
price change, unusual volume, breakouts, VWAP bands -- on a few symbols, made with the
Scanner page's "Alert me" and kept in the settings document as conditionAlerts. Judged once
a minute on the newest closed bar with the scanner's own code.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Callable

from fastapi import APIRouter, Depends, Query

from api import auth
from db import users as repo

log = logging.getLogger(__name__)
router = APIRouter(prefix="/alerts", tags=["alerts"])

CHECK_EVERY = 5          # seconds; a quote from the stream is fresh, a REST one is 15 s old at worst
REST_EVERY = 15


def _valid(a) -> bool:
    return (isinstance(a, dict) and isinstance(a.get("id"), str) and isinstance(a.get("symbol"), str)
            and isinstance(a.get("price"), (int, float)) and not isinstance(a.get("price"), bool)
            and a.get("direction") in ("above", "below"))


def due(alerts: list, prices: dict[str, float], fired: set[str]) -> list[tuple[dict, float]]:
    """The alerts these prices reach: above at or over the level, below at or under it --
    the same rule the chart applies to its bars."""
    out = []
    for a in alerts:
        if not _valid(a) or a["id"] in fired:
            continue
        p = prices.get(a["symbol"].upper().lstrip("/"))
        if p is None:
            continue
        if (p >= a["price"]) if a["direction"] == "above" else (p <= a["price"]):
            out.append(({**a, "symbol": a["symbol"].upper().lstrip("/")}, p))
    return out


def _alerts_of(user_id: int) -> list:
    row = repo.get_settings(user_id)
    try:
        doc = json.loads(row["payload"]) if row else {}
        lst = json.loads(doc.get("priceAlerts") or "[]")
        return lst if isinstance(lst, list) else []
    except (ValueError, TypeError):
        return []


def check_once(user_id: int, prices: Callable[[set[str]], dict[str, float]]) -> int:
    """One pass. Returns how many alerts fired. Never raises: a missing token or a dropped
    connection simply means no prices this time."""
    alerts = [a for a in _alerts_of(user_id) if _valid(a)]
    fired = repo.fired_alert_ids(user_id)
    symbols = {a["symbol"].upper().lstrip("/") for a in alerts if a["id"] not in fired}
    if not symbols:
        return 0
    try:
        now = prices(symbols)
    except Exception as exc:
        log.warning("alert check: no prices (%s)", exc)
        return 0
    n = 0
    for a, p in due(alerts, now, fired):
        if repo.record_alert_event(user_id, a, p):
            n += 1
            log.info("alert %s fired: %s %s %s at %s", a["id"], a["symbol"], a["direction"], a["price"], p)
    return n


# ── condition alerts: a scan on a few symbols (RSI / StochRSI / MFI, VWAP bands, ...) ──

CONDITIONS_EVERY = 60    # seconds: a condition is judged on a closed bar, at most one a minute
MAX_CONDITION_SYMBOLS = 40   # across all condition alerts, so one minute is one bounded set of requests


def _condition_alerts(user_id: int) -> list:
    row = repo.get_settings(user_id)
    try:
        doc = json.loads(row["payload"]) if row else {}
        lst = json.loads(doc.get("conditionAlerts") or "[]")
        return lst if isinstance(lst, list) else []
    except (ValueError, TypeError):
        return []


def check_conditions(user_id: int, bars_for: Callable) -> int:
    """One pass over the condition alerts. Each is validated with the scan endpoint's own
    schema and judged with the scanner's own code on the newest CLOSED bar (the forming
    one is dropped, so a match cannot appear and vanish within the bar). A symbol fires
    once, or -- in "every bar" mode -- once per bar the condition holds on."""
    from api.routers.scan import ScanRequest
    from src.analysis import scanner
    fired, n, budget = repo.fired_alert_ids(user_id), 0, MAX_CONDITION_SYMBOLS
    for raw in _condition_alerts(user_id):
        try:
            req = ScanRequest(data_source=raw.get("data_source", "schwab"), timeframe=raw["timeframe"],
                              symbols=raw["symbols"], conditions=raw["conditions"], combine=raw.get("combine", "all"))
            aid, repeat = str(raw["id"]), bool(raw.get("repeat"))
        except Exception:
            continue                                   # a malformed entry is skipped, never fatal
        conds = [c.model_dump() for c in req.conditions]
        for sym in req.symbols:
            sym = sym.upper()
            if (not repeat and f"{aid}:{sym}" in fired) or budget <= 0:
                continue
            budget -= 1
            try:
                closed = bars_for(req, sym).iloc[:-1]
                if len(closed) < 2 or not scanner.evaluate(closed, conds, req.combine)["matched"]:
                    continue
            except Exception as exc:
                log.warning("condition alert %s on %s: %s", aid, sym, exc)
                continue
            bar_time = closed.index[-1].isoformat()
            event_id = f"{aid}:{sym}:{bar_time}" if repeat else f"{aid}:{sym}"
            note = f"{raw.get('name') or 'Condition alert'} on {req.timeframe}, bar {bar_time[11:16]}"
            if repo.record_alert_event(user_id, {"id": event_id, "symbol": sym, "direction": "condition",
                                                 "price": 0.0, "note": note}, float(closed["close"].iloc[-1])):
                n += 1
                log.info("condition alert %s fired on %s at %s", aid, sym, bar_time)
    return n


def _scan_bars(req, symbol: str):
    from api.routers.scan import _bars
    return _bars(req, symbol)


class _LivePrices:
    """Stream first; REST quotes for the rest, at most every REST_EVERY seconds."""

    def __init__(self):
        self._rest_at = 0.0
        self._rest: dict[str, float] = {}

    def __call__(self, symbols: set[str]) -> dict[str, float]:
        from src.data.schwab_provider import SchwabDataProvider, _FUTURES_ROOTS
        from src.data.stream_hub import hub
        out = {}
        for s in symbols:
            hub.watch(s)
            p = hub.last_price(s) if s in _FUTURES_ROOTS else None
            if p is not None:
                out[s] = p
        missing = symbols - set(out)
        if missing and time.monotonic() - self._rest_at >= REST_EVERY:
            self._rest_at = time.monotonic()
            self._rest = {q["symbol"].upper(): float(q["last"]) for q in SchwabDataProvider().quotes(sorted(missing))}
        out.update({s: self._rest[s] for s in missing if s in self._rest})
        return out


def start_checker() -> None:
    """Run check_once for the workspace account forever, in a daemon thread. Off when
    AUTOTRADER_STREAM=0 (the test suites), like the stream itself."""
    if os.environ.get("AUTOTRADER_STREAM", "1") == "0":
        return
    prices = _LivePrices()

    def loop():
        last_conditions = 0.0
        while True:
            try:
                uid = repo.workspace_user().id
                check_once(uid, prices)
                if time.monotonic() - last_conditions >= CONDITIONS_EVERY:
                    last_conditions = time.monotonic()
                    check_conditions(uid, _scan_bars)
            except Exception:
                log.exception("alert checker")
            time.sleep(CHECK_EVERY)
    threading.Thread(target=loop, name="alert-checker", daemon=True).start()


@router.get("/events")
def events(after: int = Query(0, ge=0), user=Depends(auth.require_user)):
    """Alerts reached, oldest first, after event `after` (the newest one the app has shown)."""
    return repo.alert_events(user.id, after=after)
