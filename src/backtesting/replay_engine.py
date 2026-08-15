"""
Step-by-step replay engine.

Unlike BacktestEngine (which runs all bars at once), ReplayEngine exposes
a step() method so callers (Streamlit, a live feed, a test) can drive it
one bar at a time and observe intermediate state.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import pandas as pd

from ..data.base_provider import Bar, DataProvider
from ..broker.paper_broker import PaperBroker
from ..broker.base_broker import Order, OrderSide, OrderType
from ..strategies.base_strategy import BaseStrategy, Signal, SignalType
from .results import Trade
from .metrics import compute_metrics
from ..analysis.indicators import calc_vwap_bands
from .results import BacktestResults


@dataclass
class FrameState:
    """Snapshot of engine state after processing one bar."""
    bar: Bar
    signal: Optional[Signal]
    new_fills: list          # fills that occurred on this bar
    position: int
    portfolio_value: float
    equity: list[tuple[datetime, float]]   # full equity history so far
    completed_trades: list[Trade]
    open_trade: Optional[Trade]
    bars_processed: int
    total_bars: int
    #: Session VWAP and its +/-2 sigma bands at this bar, or None when the
    #: dataset carries no volume. Shipped at 2 sigma specifically so the client
    #: can recover sigma as (upper - vwap) / 2 and re-scale to any deviation
    #: setting without a round trip -- the same trick the backtest chart uses.
    vwap: Optional[float] = None
    vwap_upper: Optional[float] = None
    vwap_lower: Optional[float] = None


class ReplayEngine:
    """
    Drives the backtest one bar at a time.

    Usage:
        engine = ReplayEngine(strategy, symbol, ...)
        engine.load(df)
        while not engine.is_done:
            frame = engine.step()
            # render frame.bar, frame.signal, frame.completed_trades
    """

    def __init__(
        self,
        strategy: BaseStrategy,
        symbol: str,
        timeframe: str = "5m",
        initial_capital: float = 100_000.0,
        commission_per_contract: float = 2.50,
        slippage_ticks: int = 1,
        tick_size: float = 0.25,
        tick_value: float = 12.50,
        point_value: float = 50.0,
        contracts_per_trade: int = 1,
        session_start=None,
    ):
        self.strategy = strategy
        self.symbol = symbol
        self.timeframe = timeframe
        self.initial_capital = initial_capital
        self.point_value = point_value
        self.contracts_per_trade = contracts_per_trade
        # Anchors the VWAP daily reset; see calc_vwap_bands.
        self.session_start = session_start

        self._tick_size = tick_size
        self._commission = commission_per_contract
        self._slippage_ticks = slippage_ticks
        self._tick_value = tick_value

        self._df: Optional[pd.DataFrame] = None
        self._vwap = self._vwap_u = self._vwap_l = None
        self._bars: list[Bar] = []
        self._cursor: int = 0
        self._broker: Optional[PaperBroker] = None
        self._equity: list[tuple[datetime, float]] = []
        self._completed_trades: list[Trade] = []
        self._open_trade: Optional[Trade] = None
        self._seen_fill_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def load(self, df: pd.DataFrame):
        self._df = df.copy()
        self._bars = DataProvider.df_to_bars(df, self.symbol, self.timeframe)

        # VWAP is CUMULATIVE within a session, so the value at bar i depends
        # only on bars 0..i. Computing the whole series once and indexing it by
        # the cursor is therefore identical to recomputing over "bars so far"
        # at every step -- no look-ahead -- but costs O(n) in total instead of
        # O(n^2). Reuses calc_vwap_bands rather than reimplementing it.
        vol = df["volume"] if "volume" in df else None
        # Present when the frame was built by resample_ohlcv(with_vwap_price=True):
        # each bar's own volume-weighted price, which is what a broker platform's
        # VWAP study accumulates. Absent, calc_vwap_bands falls back to (H+L+C)/3.
        price = df["vwap_price"] if "vwap_price" in df else None
        try:
            v, u, l = calc_vwap_bands(df["high"], df["low"], df["close"], vol,
                                      num_dev=2.0, session_start=self.session_start,
                                      price=price)
            self._vwap = v.to_numpy(dtype=float)
            self._vwap_u = u.to_numpy(dtype=float)
            self._vwap_l = l.to_numpy(dtype=float)
        except Exception:
            # A dataset without usable volume yields all-NaN; treat any failure
            # as "no VWAP available" rather than breaking playback.
            self._vwap = self._vwap_u = self._vwap_l = None

        self.reset()

    def reset(self):
        self._cursor = 0
        self._equity = []
        self._completed_trades = []
        self._open_trade = None
        self._seen_fill_ids = set()
        self._broker = PaperBroker(
            initial_capital=self.initial_capital,
            commission_per_contract=self._commission,
            slippage_ticks=self._slippage_ticks,
            tick_size=self._tick_size,
            tick_value=self._tick_value,
        )
        self.strategy.reset()

    # ------------------------------------------------------------------
    # Stepping
    # ------------------------------------------------------------------

    @property
    def is_done(self) -> bool:
        return self._cursor >= len(self._bars)

    @property
    def progress(self) -> tuple[int, int]:
        return self._cursor, len(self._bars)

    def step(self) -> FrameState:
        if self.is_done:
            raise StopIteration("Replay is complete.")

        bar = self._bars[self._cursor]
        bars_so_far = self._df.iloc[: self._cursor + 1]

        # Process broker fills against this bar
        self._broker.process_bar(
            bar.symbol, bar.open, bar.high, bar.low, bar.close, bar.timestamp
        )
        new_fills = self._reconcile_fills()

        # Portfolio value
        pos = self._broker.get_position(self.symbol)
        unrealised = self._unrealised_pnl(pos, bar.close)
        pv = self._broker.get_cash() + unrealised
        self._equity.append((bar.timestamp, pv))

        # Strategy signal
        signal = self.strategy.on_bar(bars_so_far, bar, pos)
        if signal:
            self._handle_signal(signal, pos)

        self._cursor += 1

        return FrameState(
            bar=bar,
            signal=signal,
            new_fills=new_fills,
            position=self._broker.get_position(self.symbol),
            portfolio_value=pv,
            equity=list(self._equity),
            completed_trades=list(self._completed_trades),
            open_trade=self._open_trade,
            bars_processed=self._cursor,
            total_bars=len(self._bars),
            **self._vwap_at(self._cursor - 1),
        )

    def vwap_at(self, i: int) -> dict:
        """Public view of one bar's VWAP triple, for backfilling a late pane."""
        return self._vwap_at(i)

    def _vwap_at(self, i: int) -> dict:
        """VWAP/band values at bar `i`, as plain floats (NaN -> None)."""
        if self._vwap is None or i < 0 or i >= len(self._vwap):
            return {"vwap": None, "vwap_upper": None, "vwap_lower": None}
        import math
        def clean(a):
            x = float(a[i])
            return None if math.isnan(x) else x
        return {"vwap": clean(self._vwap),
                "vwap_upper": clean(self._vwap_u),
                "vwap_lower": clean(self._vwap_l)}

    def get_results(self) -> BacktestResults:
        """Build a full BacktestResults from current engine state."""
        # Force-close any open position
        if self._open_trade and self._bars:
            last = self._bars[min(self._cursor, len(self._bars)) - 1]
            self._close_trade(last.close, last.timestamp, 0.0, "forced_close")

        eq = pd.Series(
            {ts: val for ts, val in self._equity}, name="equity"
        )
        r = BacktestResults(
            symbol=self.symbol,
            strategy_name=self.strategy.name,
            timeframe=self.timeframe,
            start_date=self._bars[0].timestamp if self._bars else datetime.now(),
            end_date=self._bars[self._cursor - 1].timestamp if self._cursor else datetime.now(),
            initial_capital=self.initial_capital,
            trades=list(self._completed_trades),
            equity_curve=eq,
            price_data=self._df if self._df is not None else pd.DataFrame(),
        )
        compute_metrics(r)
        return r

    # ------------------------------------------------------------------
    # Internal helpers (same logic as BacktestEngine)
    # ------------------------------------------------------------------

    def _handle_signal(self, signal: Signal, current_pos: int):
        def mkt(side: OrderSide, qty: int):
            return Order(
                symbol=self.symbol, side=side, quantity=qty,
                order_type=OrderType.MARKET, strategy_tag=signal.strategy_name,
            )
        if signal.signal_type == SignalType.BUY and current_pos <= 0:
            if current_pos < 0:
                self._broker.submit_order(mkt(OrderSide.BUY, abs(current_pos)))
            self._broker.submit_order(mkt(OrderSide.BUY, self.contracts_per_trade))
        elif signal.signal_type == SignalType.SELL and current_pos >= 0:
            if current_pos > 0:
                self._broker.submit_order(mkt(OrderSide.SELL, current_pos))
            self._broker.submit_order(mkt(OrderSide.SELL, self.contracts_per_trade))
        elif signal.signal_type == SignalType.CLOSE and current_pos != 0:
            side = OrderSide.SELL if current_pos > 0 else OrderSide.BUY
            self._broker.submit_order(mkt(side, abs(current_pos)))

    def _reconcile_fills(self) -> list:
        new = []
        for fill in self._broker.get_fills():
            if fill.order_id in self._seen_fill_ids:
                continue
            self._seen_fill_ids.add(fill.order_id)
            new.append(fill)

            if fill.side == OrderSide.BUY:
                if self._open_trade and self._open_trade.direction == "SHORT":
                    self._close_trade(fill.fill_price, fill.filled_at, fill.commission, fill.order_id)
                else:
                    self._open_trade = Trade(
                        symbol=fill.symbol, direction="LONG",
                        quantity=fill.quantity, entry_time=fill.filled_at,
                        entry_price=fill.fill_price, exit_time=None, exit_price=None,
                        pnl=0.0, commission=fill.commission,
                        strategy=fill.strategy_tag, entry_order_id=fill.order_id,
                    )
            elif fill.side == OrderSide.SELL:
                if self._open_trade and self._open_trade.direction == "LONG":
                    self._close_trade(fill.fill_price, fill.filled_at, fill.commission, fill.order_id)
                else:
                    self._open_trade = Trade(
                        symbol=fill.symbol, direction="SHORT",
                        quantity=fill.quantity, entry_time=fill.filled_at,
                        entry_price=fill.fill_price, exit_time=None, exit_price=None,
                        pnl=0.0, commission=fill.commission,
                        strategy=fill.strategy_tag, entry_order_id=fill.order_id,
                    )
        return new

    def _close_trade(self, price: float, ts: datetime, commission: float, order_id: str):
        t = self._open_trade
        t.exit_time = ts
        t.exit_price = price
        t.exit_order_id = order_id
        t.commission += commission
        if t.direction == "LONG":
            gross = (price - t.entry_price) * t.quantity * self.point_value
        else:
            gross = (t.entry_price - price) * t.quantity * self.point_value
        t.pnl = gross - t.commission
        self._completed_trades.append(t)
        self._open_trade = None

    def _unrealised_pnl(self, position: int, price: float) -> float:
        if position == 0 or self._open_trade is None:
            return 0.0
        ep = self._open_trade.entry_price
        qty = abs(position)
        return ((price - ep) if position > 0 else (ep - price)) * qty * self.point_value
