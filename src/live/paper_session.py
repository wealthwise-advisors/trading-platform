"""A strategy running forward on live bars, filling against a simulated book.

WHAT THIS IS FOR. A backtest tells you what a strategy did to history it has
already seen. This tells you what it does to bars arriving for the first time
-- the same code path, the same signals, the same guard, the same order
objects -- with the fills simulated instead of sent. It is the step between
"the numbers look good" and "this is allowed to touch an account", and the
whole point is that it is indistinguishable from the real thing on every side
except the one that costs money.

NOTHING HERE CAN REACH A BROKER. The session takes a BaseBroker and this
module never constructs one; api/routers/live.py hands it a PaperBroker.
Pointing it at a live broker is a deliberate edit in a different file, made by
someone who meant to, which is the only way that change should ever be
possible.

Every order still goes through OrderGuard first. Not because a simulated fill
can hurt anyone, but because the guard is the part that has to be exercised:
a rail first tested on the day it protects real money has not been tested.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd
from loguru import logger

from ..broker.base_broker import BaseBroker, Order, OrderSide
from ..broker.order_guard import GuardLimits, OrderGuard, OrderRejected
from ..strategies.base_strategy import BaseStrategy, SignalType


@dataclass
class SessionEvent:
    """One line of the session's log, for the UI to show."""

    at: datetime
    kind: str          # "signal" | "order" | "fill" | "rejected" | "info"
    text: str


@dataclass
class PaperSession:
    """One strategy, one symbol, running forward.

    Thread-safe because bars arrive on a poller while the API reads status on
    a request thread -- two threads touching one broker's position book is
    exactly the race that produces a double order.
    """

    strategy: BaseStrategy
    broker: BaseBroker
    symbol: str
    contracts: int = 1
    guard: OrderGuard = field(default_factory=OrderGuard)

    started_at: datetime = field(default_factory=datetime.now)
    stopped_at: datetime | None = None
    bars_seen: int = 0
    #: The timestamp of the last bar acted on. THE DUPLICATE GUARD. Bars
    #: arrive from a browser, and a browser reloads, retries, and runs two
    #: tabs. A bar at or before this one has already been decided about, and
    #: deciding again is how one signal becomes two orders.
    last_bar_ts: datetime | None = None
    duplicates_ignored: int = 0
    #: Wall clock of the last contact from the dashboard. What "the browser
    #: went away" is measured against -- a bar timestamp cannot tell you that,
    #: because a quiet market and a closed laptop look identical in bar data.
    last_seen_at: datetime = field(default_factory=datetime.now)
    events: list[SessionEvent] = field(default_factory=list)

    _bars: pd.DataFrame = field(default_factory=pd.DataFrame)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    # ── lifecycle ─────────────────────────────────────────────────────────
    def __post_init__(self) -> None:
        self._log("info", f"paper session started: {self.strategy.name} on {self.symbol}")

    @property
    def running(self) -> bool:
        return self.stopped_at is None and not self.guard.halted

    def heartbeat(self) -> None:
        """The dashboard saying it is still there, between bars.

        Needed because bars are minutes apart: without it a session would look
        abandoned for most of its life on any timeframe above a minute.
        """
        with self._lock:
            self.last_seen_at = datetime.now()

    def is_stale(self, timeout_seconds: float, now: datetime | None = None) -> bool:
        """Has the dashboard stopped talking to us?

        A browser that closes does not get to say goodbye -- a tab can be
        killed, a laptop can sleep, a network can drop. So the session watches
        for silence rather than trusting a farewell that may never come.
        """
        now = now or datetime.now()
        return (now - self.last_seen_at).total_seconds() > timeout_seconds

    def stop(self, reason: str = "stopped by request") -> None:
        with self._lock:
            if self.stopped_at is None:
                self.stopped_at = datetime.now()
                self._log("info", reason)

    def halt(self, reason: str) -> None:
        """Stop and refuse anything further. One way, as the guard is."""
        with self._lock:
            self.guard.halt(reason)
            self.stop(f"halted: {reason}")

    # ── the loop ──────────────────────────────────────────────────────────
    def on_bar(self, bar) -> None:
        """Feed one newly closed bar through the strategy.

        A bar that is still forming must not be passed here. A strategy that
        sees a live bar's high before the bar has closed is reading the future
        by one tick, and a paper session that flatters itself is worse than no
        paper session at all.
        """
        with self._lock:
            if not self.running:
                return
            self.last_seen_at = datetime.now()

            # AT OR BEFORE THE LAST BAR: already decided about. This is the
            # reconnect case -- a dashboard that comes back and re-sends the
            # last few closed bars must not re-open the trades they caused --
            # and equally the double-tab and retry cases. Counted rather than
            # silently dropped, so a feed that is misbehaving is visible.
            if self.last_bar_ts is not None and bar.timestamp <= self.last_bar_ts:
                self.duplicates_ignored += 1
                return
            self.last_bar_ts = bar.timestamp

            self.bars_seen += 1
            row = pd.DataFrame(
                [{"open": bar.open, "high": bar.high, "low": bar.low,
                  "close": bar.close, "volume": getattr(bar, "volume", 0)}],
                index=[bar.timestamp],
            )
            self._bars = row if self._bars.empty else pd.concat([self._bars, row])

            # Fills FIRST, then the signal. An order resting from the previous
            # bar fills against this bar's range before the strategy is asked
            # what to do next -- the other order would let a strategy act on a
            # position it does not have yet.
            if hasattr(self.broker, "process_bar"):
                self.broker.process_bar(self.symbol, bar.open, bar.high, bar.low,
                                        bar.close, bar.timestamp)

            position = self.broker.get_position(self.symbol)
            try:
                signal = self.strategy.on_bar(self._bars, bar, position)
            except Exception as e:
                # A strategy that throws is a strategy whose next signal cannot
                # be trusted, so the session stops rather than skipping a bar
                # and carrying on with a position it may not understand.
                self.halt(f"strategy raised: {e}")
                logger.exception("paper session: strategy raised")
                return

            if signal is None:
                return
            self._log("signal", f"{signal.signal_type.value} @ {signal.price:.2f}"
                                + (f" -- {signal.reason}" if signal.reason else ""))
            self._act(signal, position, bar.timestamp)

    # ── turning a signal into an order ────────────────────────────────────
    def _act(self, signal, position: int, now: datetime) -> None:
        if signal.signal_type is SignalType.BUY:
            side, qty = OrderSide.BUY, self.contracts
        elif signal.signal_type is SignalType.SELL:
            side, qty = OrderSide.SELL, self.contracts
        else:  # CLOSE
            if position == 0:
                return
            side = OrderSide.SELL if position > 0 else OrderSide.BUY
            qty = abs(position)

        order = Order(symbol=self.symbol, side=side, quantity=qty,
                      strategy_tag=self.strategy.name, created_at=now)
        try:
            self.guard.check(order, current_position=position, now=now)
        except OrderRejected as e:
            # Refused, and the session keeps going: a rejection is the rail
            # doing its job, not a fault. It is logged where someone will see
            # it, because a rail that refuses silently teaches nobody anything.
            self._log("rejected", str(e))
            return

        self.broker.submit_order(order)
        self.guard.record(now=now)
        self._log("order", f"{side.value} {qty} {self.symbol} ({order.order_id})")

    # ── what the UI reads ─────────────────────────────────────────────────
    def status(self) -> dict:
        with self._lock:
            fills = self.broker.get_fills()
            return {
                "running": self.running,
                "mode": "paper",
                "strategy": self.strategy.name,
                "symbol": self.symbol,
                "contracts": self.contracts,
                "started_at": self.started_at.isoformat(timespec="seconds"),
                "stopped_at": self.stopped_at.isoformat(timespec="seconds") if self.stopped_at else None,
                "bars_seen": self.bars_seen,
                "duplicates_ignored": self.duplicates_ignored,
                "last_bar_at": self.last_bar_ts.isoformat(timespec="seconds") if self.last_bar_ts else None,
                "position": self.broker.get_position(self.symbol),
                "cash": round(self.broker.get_cash(), 2),
                "fills": len(fills),
                "orders_sent": self.guard.orders_sent,
                "orders_remaining": self.guard.orders_remaining,
                "halted": self.guard.halted,
                "halt_reason": self.guard.halt_reason,
                "events": [
                    {"at": e.at.isoformat(timespec="seconds"), "kind": e.kind, "text": e.text}
                    # Newest first, and capped: this is a status panel, not an
                    # audit log, and an unbounded list in memory is a leak.
                    for e in list(reversed(self.events))[:50]
                ],
            }

    def _log(self, kind: str, text: str) -> None:
        self.events.append(SessionEvent(at=datetime.now(), kind=kind, text=text))
        if len(self.events) > 500:
            del self.events[:-500]


def default_limits(symbol: str, contracts: int) -> GuardLimits:
    """The rails a paper session runs with.

    The same ceilings a live session would get. Loosening them for paper would
    mean the rails are first exercised on the day they matter, which is the
    one day they must already be known to work.
    """
    return GuardLimits(
        max_contracts_per_order=max(1, contracts),
        max_position_contracts=max(1, contracts) * 2,
        max_orders_per_session=50,
        min_seconds_between_orders=1.0,
        allowed_symbols=frozenset({symbol}),
    )
