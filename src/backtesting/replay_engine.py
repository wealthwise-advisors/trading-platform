"""
Step-by-step replay engine.

Unlike BacktestEngine (which runs all bars at once), ReplayEngine exposes
a step() method so callers (Streamlit, a live feed, a test) can drive it
one bar at a time and observe intermediate state.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import pandas as pd
from loguru import logger

from ..data.base_provider import Bar, DataProvider
from ..broker.paper_broker import PaperBroker
from ..broker.base_broker import Order, OrderSide, OrderType
from ..strategies.base_strategy import BaseStrategy, Signal, SignalType
from .results import Trade
from .metrics import compute_metrics
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
    ):
        self.strategy = strategy
        self.symbol = symbol
        self.timeframe = timeframe
        self.initial_capital = initial_capital
        self.point_value = point_value
        self.contracts_per_trade = contracts_per_trade

        self._tick_size = tick_size
        self._commission = commission_per_contract
        self._slippage_ticks = slippage_ticks
        self._tick_value = tick_value

        self._df: Optional[pd.DataFrame] = None
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
        )

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
