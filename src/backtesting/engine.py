"""
Event-driven backtesting engine for futures.

Flow per bar:
  1. Feed bar to strategy -> optional Signal
  2. Convert Signal -> Order -> PaperBroker
  3. PaperBroker.process_bar() -> fills pending orders against this bar
  4. Reconcile fills into round-trip Trade objects
  5. Track equity curve
"""

from datetime import datetime
from typing import Optional
import pandas as pd
from loguru import logger

from ..data.base_provider import Bar, DataProvider
from ..broker.paper_broker import PaperBroker
from ..broker.base_broker import Order, OrderSide, OrderType
from ..strategies.base_strategy import BaseStrategy, Signal, SignalType
from .results import BacktestResults, Trade
from .metrics import compute_metrics


class BacktestEngine:
    def __init__(
        self,
        data_provider: DataProvider,
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
        self.data_provider = data_provider
        self.strategy = strategy
        self.symbol = symbol
        self.timeframe = timeframe
        self.initial_capital = initial_capital
        self.point_value = point_value
        self.contracts_per_trade = contracts_per_trade

        self.broker = PaperBroker(
            initial_capital=initial_capital,
            commission_per_contract=commission_per_contract,
            slippage_ticks=slippage_ticks,
            tick_size=tick_size,
            tick_value=tick_value,
        )

        self._bars: list[Bar] = []
        self._equity: list[tuple[datetime, float]] = []
        self._open_trade: Optional[Trade] = None
        self._completed_trades: list[Trade] = []
        self._seen_fill_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, start: datetime, end: datetime) -> BacktestResults:
        logger.info(
            f"Backtest: {self.strategy.name} | {self.symbol} | "
            f"{start.date()} -> {end.date()}"
        )

        df = self.data_provider.load(self.symbol, start, end, self.timeframe)
        bars = DataProvider.df_to_bars(df, self.symbol, self.timeframe)
        self.strategy.reset()

        for bar in bars:
            self._on_bar(bar, df)

        # Force-close any open position at last bar close
        if self._open_trade and bars:
            last = bars[-1]
            self._force_close(last.close, last.timestamp)

        equity_series = pd.Series(
            {ts: val for ts, val in self._equity},
            name="equity",
        )

        results = BacktestResults(
            symbol=self.symbol,
            strategy_name=self.strategy.name,
            timeframe=self.timeframe,
            start_date=start,
            end_date=end,
            initial_capital=self.initial_capital,
            trades=self._completed_trades,
            equity_curve=equity_series,
            price_data=df,
        )
        compute_metrics(results)
        logger.info(
            f"Done: {results.total_trades} trades | "
            f"P&L ${results.total_pnl:,.0f} | "
            f"Return {results.total_return_pct:.1f}% | "
            f"Win {results.win_rate:.0f}%"
        )
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_bar(self, bar: Bar, full_df: pd.DataFrame):
        self._bars.append(bar)

        # Fill any orders placed on the previous bar
        self.broker.process_bar(
            bar.symbol, bar.open, bar.high, bar.low, bar.close, bar.timestamp
        )
        self._reconcile_fills()

        # Portfolio value = cash + unrealised P&L
        pos = self.broker.get_position(self.symbol)
        unrealised = self._unrealised_pnl(pos, bar.close)
        self._equity.append((bar.timestamp, self.broker.get_cash() + unrealised))

        # Ask strategy for a signal
        bars_so_far = full_df.loc[: bar.timestamp]
        signal = self.strategy.on_bar(bars_so_far, bar, pos)
        if signal:
            self._handle_signal(signal, pos)

    def _handle_signal(self, signal: Signal, current_pos: int):
        def market_order(side: OrderSide, qty: int) -> Order:
            return Order(
                symbol=self.symbol,
                side=side,
                quantity=qty,
                order_type=OrderType.MARKET,
                strategy_tag=signal.strategy_name,
            )

        if signal.signal_type == SignalType.BUY and current_pos <= 0:
            if current_pos < 0:
                self.broker.submit_order(market_order(OrderSide.BUY, abs(current_pos)))
            self.broker.submit_order(market_order(OrderSide.BUY, self.contracts_per_trade))

        elif signal.signal_type == SignalType.SELL and current_pos >= 0:
            if current_pos > 0:
                self.broker.submit_order(market_order(OrderSide.SELL, current_pos))
            self.broker.submit_order(market_order(OrderSide.SELL, self.contracts_per_trade))

        elif signal.signal_type == SignalType.CLOSE and current_pos != 0:
            side = OrderSide.SELL if current_pos > 0 else OrderSide.BUY
            self.broker.submit_order(market_order(side, abs(current_pos)))

    def _reconcile_fills(self):
        for fill in self.broker.get_fills():
            if fill.order_id in self._seen_fill_ids:
                continue
            self._seen_fill_ids.add(fill.order_id)

            if fill.side == OrderSide.BUY:
                if self._open_trade and self._open_trade.direction == "SHORT":
                    self._close_trade(fill.fill_price, fill.filled_at, fill.commission, fill.order_id)
                else:
                    self._open_trade = Trade(
                        symbol=fill.symbol,
                        direction="LONG",
                        quantity=fill.quantity,
                        entry_time=fill.filled_at,
                        entry_price=fill.fill_price,
                        exit_time=None,
                        exit_price=None,
                        pnl=0.0,
                        commission=fill.commission,
                        strategy=fill.strategy_tag,
                        entry_order_id=fill.order_id,
                    )

            elif fill.side == OrderSide.SELL:
                if self._open_trade and self._open_trade.direction == "LONG":
                    self._close_trade(fill.fill_price, fill.filled_at, fill.commission, fill.order_id)
                else:
                    self._open_trade = Trade(
                        symbol=fill.symbol,
                        direction="SHORT",
                        quantity=fill.quantity,
                        entry_time=fill.filled_at,
                        entry_price=fill.fill_price,
                        exit_time=None,
                        exit_price=None,
                        pnl=0.0,
                        commission=fill.commission,
                        strategy=fill.strategy_tag,
                        entry_order_id=fill.order_id,
                    )

    def _close_trade(self, price: float, timestamp: datetime, commission: float, order_id: str):
        t = self._open_trade
        t.exit_time = timestamp
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

    def _force_close(self, price: float, timestamp: datetime):
        if self._open_trade is None:
            return
        self._close_trade(price, timestamp, commission=0.0, order_id="forced_close")

    def _unrealised_pnl(self, position: int, current_price: float) -> float:
        if position == 0 or self._open_trade is None:
            return 0.0
        ep = self._open_trade.entry_price
        qty = abs(position)
        if position > 0:
            return (current_price - ep) * qty * self.point_value
        return (ep - current_price) * qty * self.point_value
