"""Simulated broker used by the backtesting engine and for paper trading."""

from datetime import datetime
from loguru import logger

from .base_broker import BaseBroker, Fill, Order, OrderSide, OrderStatus, OrderType


class PaperBroker(BaseBroker):
    def __init__(
        self,
        initial_capital: float = 100_000.0,
        commission_per_contract: float = 2.50,
        slippage_ticks: int = 1,
        tick_size: float = 0.25,
        tick_value: float = 12.50,
    ):
        self._cash = initial_capital
        self._initial_capital = initial_capital
        self._commission = commission_per_contract
        self._slippage_ticks = slippage_ticks
        self._tick_size = tick_size
        self._tick_value = tick_value
        self._positions: dict[str, int] = {}      # symbol -> net contracts
        self._open_orders: dict[str, Order] = {}
        self._fills: list[Fill] = []
        self._pending_orders: list[Order] = []

    # ------------------------------------------------------------------
    # BaseBroker interface
    # ------------------------------------------------------------------

    def submit_order(self, order: Order) -> str:
        order.status = OrderStatus.OPEN
        self._pending_orders.append(order)
        return order.order_id

    def cancel_order(self, order_id: str) -> bool:
        for o in self._pending_orders:
            if o.order_id == order_id:
                o.status = OrderStatus.CANCELLED
                self._pending_orders.remove(o)
                return True
        return False

    def get_position(self, symbol: str) -> int:
        return self._positions.get(symbol, 0)

    def get_cash(self) -> float:
        return self._cash

    def get_fills(self) -> list[Fill]:
        return list(self._fills)

    # ------------------------------------------------------------------
    # Called by the backtest engine on each bar close
    # ------------------------------------------------------------------

    def process_bar(self, symbol: str, bar_open: float, bar_high: float, bar_low: float, bar_close: float, timestamp: datetime):
        """Attempt to fill any pending orders against this bar's prices."""
        filled = []
        for order in self._pending_orders:
            if order.symbol != symbol:
                continue

            fill_price = self._get_fill_price(order, bar_open, bar_high, bar_low, bar_close)
            if fill_price is None:
                continue

            commission = self._commission * order.quantity
            fill = Fill(
                order_id=order.order_id,
                symbol=symbol,
                side=order.side,
                quantity=order.quantity,
                fill_price=fill_price,
                commission=commission,
                filled_at=timestamp,
                strategy_tag=order.strategy_tag,
            )
            self._fills.append(fill)

            sign = 1 if order.side == OrderSide.BUY else -1
            self._positions[symbol] = self._positions.get(symbol, 0) + sign * order.quantity

            # Update cash: PnL on fill is zero at entry; subtract commission
            self._cash -= commission

            order.status = OrderStatus.FILLED
            filled.append(order)
            logger.debug(f"Fill: {order.side.value} {order.quantity} {symbol} @ {fill_price:.2f}")

        for o in filled:
            self._pending_orders.remove(o)

    def _get_fill_price(self, order: Order, o: float, h: float, l: float, c: float) -> float | None:
        slippage = self._slippage_ticks * self._tick_size

        if order.order_type == OrderType.MARKET:
            if order.side == OrderSide.BUY:
                return o + slippage
            return o - slippage

        if order.order_type == OrderType.LIMIT:
            if order.side == OrderSide.BUY and l <= order.limit_price:
                return min(order.limit_price + slippage, o)
            if order.side == OrderSide.SELL and h >= order.limit_price:
                return max(order.limit_price - slippage, o)

        if order.order_type == OrderType.STOP:
            if order.side == OrderSide.BUY and h >= order.stop_price:
                return order.stop_price + slippage
            if order.side == OrderSide.SELL and l <= order.stop_price:
                return order.stop_price - slippage

        return None

    @property
    def initial_capital(self) -> float:
        return self._initial_capital
