"""A strategy running forward on live bars, filling on paper.

The session is the thing that will one day be pointed at a real broker, so it
is tested as if it already were: that it cannot act twice on one bar, that a
throwing strategy stops it rather than being skipped, that the guard is
actually consulted, and that fills settle before the next signal is asked for.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from src.broker.order_guard import GuardLimits, OrderGuard
from src.broker.paper_broker import PaperBroker
from src.live.paper_session import PaperSession, default_limits
from src.strategies.base_strategy import BaseStrategy, Signal, SignalType


@dataclass
class _Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 100


class _Scripted(BaseStrategy):
    """Emits a scripted list of signals, one per bar."""

    def __init__(self, script):
        super().__init__(name="scripted")
        self.script = list(script)
        self.seen_positions = []

    def on_bar(self, bars_df, current_bar, position):
        self.seen_positions.append(position)
        if not self.script:
            return None
        kind = self.script.pop(0)
        if kind is None:
            return None
        return Signal(signal_type=kind, strategy_name=self.name,
                      timestamp=current_bar.timestamp, price=current_bar.close)


class _Exploding(BaseStrategy):
    def __init__(self):
        super().__init__(name="exploding")

    def on_bar(self, bars_df, current_bar, position):
        raise ValueError("indicator not ready")


def _session(script, *, contracts=1, symbol="ES"):
    return PaperSession(
        strategy=_Scripted(script),
        broker=PaperBroker(initial_capital=100_000.0),
        symbol=symbol,
        contracts=contracts,
        guard=OrderGuard(limits=default_limits(symbol, contracts)),
    )


def _bars(n, start=4500.0, step=1.0, t0=datetime(2026, 9, 18, 9, 30)):
    return [_Bar(t0 + timedelta(minutes=i), start + i * step, start + i * step + 1,
                 start + i * step - 1, start + i * step) for i in range(n)]


# ── it actually trades ────────────────────────────────────────────────────
def test_a_buy_signal_becomes_an_order_and_then_a_position():
    s = _session([SignalType.BUY, None, None])
    for b in _bars(3):
        s.on_bar(b)
    assert s.broker.get_position("ES") == 1
    assert s.status()["orders_sent"] == 1


def test_a_close_signal_flattens_whatever_is_held():
    s = _session([SignalType.BUY, None, SignalType.CLOSE, None])
    for b in _bars(4):
        s.on_bar(b)
    assert s.broker.get_position("ES") == 0


def test_close_with_no_position_does_nothing():
    s = _session([SignalType.CLOSE])
    for b in _bars(2):
        s.on_bar(b)
    assert s.status()["orders_sent"] == 0


# ── the guard is really in the path ───────────────────────────────────────
def test_the_guard_refuses_an_oversized_position_and_the_session_survives():
    """A rejection is the rail working, not a fault -- the session keeps
    running and says so."""
    s = PaperSession(
        strategy=_Scripted([SignalType.BUY] * 6),
        broker=PaperBroker(),
        symbol="ES",
        contracts=1,
        guard=OrderGuard(limits=GuardLimits(
            allowed_symbols=frozenset({"ES"}), max_position_contracts=2,
            min_seconds_between_orders=0)),
    )
    for b in _bars(6):
        s.on_bar(b)
    assert abs(s.broker.get_position("ES")) <= 2
    assert s.running
    assert any(e["kind"] == "rejected" for e in s.status()["events"])


def test_a_symbol_outside_the_allow_list_never_reaches_the_broker():
    s = PaperSession(
        strategy=_Scripted([SignalType.BUY]),
        broker=PaperBroker(),
        symbol="NQ",
        contracts=1,
        guard=OrderGuard(limits=GuardLimits(allowed_symbols=frozenset({"ES"}))),
    )
    for b in _bars(2):
        s.on_bar(b)
    assert s.broker.get_position("NQ") == 0
    assert s.status()["orders_sent"] == 0


# ── failure modes ─────────────────────────────────────────────────────────
def test_a_throwing_strategy_halts_the_session_rather_than_skipping_the_bar():
    """Its next signal cannot be trusted, so nothing more is sent."""
    s = PaperSession(strategy=_Exploding(), broker=PaperBroker(), symbol="ES",
                     guard=OrderGuard(limits=default_limits("ES", 1)))
    s.on_bar(_bars(1)[0])
    assert not s.running
    assert s.guard.halted
    assert "strategy raised" in (s.guard.halt_reason or "")


def test_a_stopped_session_ignores_further_bars():
    s = _session([SignalType.BUY] * 4)
    s.stop()
    for b in _bars(4):
        s.on_bar(b)
    assert s.bars_seen == 0
    assert s.status()["orders_sent"] == 0


def test_halting_is_one_way():
    s = _session([None])
    s.halt("manual")
    s.stop("try again")
    assert not s.running


# ── ordering within a bar ─────────────────────────────────────────────────
def test_resting_fills_settle_before_the_next_signal_is_asked_for():
    """The strategy must see the position it already has, or it will act on a
    holding it does not know about."""
    s = _session([SignalType.BUY, None, None])
    bars = _bars(3)
    for b in bars:
        s.on_bar(b)
    # bar 1: no position yet. bar 2: the bar-1 order has filled.
    assert s.strategy.seen_positions[0] == 0
    assert s.strategy.seen_positions[1] == 1


def test_status_reports_what_the_ui_needs():
    s = _session([SignalType.BUY, None])
    for b in _bars(2):
        s.on_bar(b)
    st = s.status()
    assert st["mode"] == "paper"
    assert st["running"] is True
    assert st["symbol"] == "ES"
    assert st["bars_seen"] == 2
    assert st["orders_sent"] == 1
    assert isinstance(st["events"], list) and st["events"]


def test_the_event_log_is_capped_so_a_long_session_cannot_grow_without_bound():
    s = _session([None] * 5)
    for i in range(600):
        s._log("info", f"line {i}")
    assert len(s.events) <= 500
    assert len(s.status()["events"]) <= 50


def test_default_limits_are_the_same_rails_a_live_session_would_get():
    """Loosening them for paper would mean the rails are first exercised on
    the day they matter."""
    lim = default_limits("ES", 2)
    assert lim.allowed_symbols == frozenset({"ES"})
    assert lim.max_contracts_per_order == 2
    assert lim.max_position_contracts == 4
    assert lim.min_seconds_between_orders >= 1.0
