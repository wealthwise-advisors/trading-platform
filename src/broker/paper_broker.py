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
        self._avg_price: dict[str, float] = {}    # symbol -> average entry price of the open position
        self._point_value = tick_value / tick_size if tick_size else 0.0
        self._open_orders: dict[str, Order] = {}
        self._fills: list[Fill] = []
        self._pending_orders: list[Order] = []
        self._filled_ids: set[str] = set()

    # ------------------------------------------------------------------
    # BaseBroker interface
    # ------------------------------------------------------------------

    def submit_order(self, order: Order) -> str:
        order.status = OrderStatus.OPEN
        self._pending_orders.append(order)
        return order.order_id

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a working order, and with it any bracket legs waiting on it."""
        found = False
        for o in list(self._pending_orders):
            if o.order_id == order_id or o.parent_id == order_id:
                o.status = OrderStatus.CANCELLED
                self._pending_orders.remove(o)
                found = found or o.order_id == order_id
        return found

    def working_orders(self) -> list[Order]:
        """Orders still waiting to fill, in the order they were placed."""
        return [o for o in self._pending_orders if o.status == OrderStatus.OPEN]

    def get_position(self, symbol: str) -> int:
        return self._positions.get(symbol, 0)

    def get_cash(self) -> float:
        return self._cash

    def get_fills(self) -> list[Fill]:
        return list(self._fills)

    # ------------------------------------------------------------------
    # Called by the backtest engine on each bar close
    # ------------------------------------------------------------------

    #: Within one bar, market orders first, then stops, then limits: when a bar reaches
    #: both a bracket's stop and its target, the order of prices inside it is unknown,
    #: and the stop filling first is the assumption that never flatters the result.
    _PRIORITY = {OrderType.MARKET: 0, OrderType.STOP: 1, OrderType.STOP_LIMIT: 1, OrderType.LIMIT: 2}

    def process_bar(self, symbol: str, bar_open: float, bar_high: float, bar_low: float, bar_close: float, timestamp: datetime):
        """Attempt to fill any pending orders against this bar's prices."""
        ohlc = (bar_open, bar_high, bar_low, bar_close)
        queue = sorted((o for o in self._pending_orders if o.symbol == symbol and self._active(o)),
                       key=lambda o: self._PRIORITY[o.order_type])
        while queue:
            order = queue.pop(0)
            if order.status != OrderStatus.OPEN:
                continue                                   # cancelled by a sibling meanwhile
            fill_price = self._get_fill_price(order, *ohlc)
            if fill_price is None:
                continue
            self._book(order, fill_price, timestamp)
            for o in list(self._pending_orders):           # the rest of its OCO group
                if order.oco_group and o.oco_group == order.oco_group and o.status == OrderStatus.OPEN:
                    o.status = OrderStatus.CANCELLED
                    self._pending_orders.remove(o)
            # Its bracket legs start now. In this same bar only the stops may count: the
            # entry's bar may have reached the stop after the fill; that it reached the
            # target after it is the assumption that would flatter.
            queue[:0] = [o for o in self._pending_orders
                         if o.parent_id == order.order_id and o.order_type in (OrderType.STOP, OrderType.STOP_LIMIT)]
        # Trailing stops follow the bar AFTER it was checked against their old level.
        for o in self._pending_orders:
            if o.symbol == symbol and o.trail_ticks and o.status == OrderStatus.OPEN and self._active(o):
                gap = o.trail_ticks * self._tick_size
                o.stop_price = (max(o.stop_price, bar_high - gap) if o.side == OrderSide.SELL
                                else min(o.stop_price, bar_low + gap))

    def _active(self, order: Order) -> bool:
        return order.parent_id is None or order.parent_id in self._filled_ids

    def _book(self, order: Order, fill_price: float, timestamp: datetime) -> None:
        commission = self._commission * order.quantity
        self._fills.append(Fill(
            order_id=order.order_id, symbol=order.symbol, side=order.side, quantity=order.quantity,
            fill_price=fill_price, commission=commission, filled_at=timestamp,
            strategy_tag=order.strategy_tag,
        ))
        sign = 1 if order.side == OrderSide.BUY else -1
        self._realise(order.symbol, sign * order.quantity, fill_price)
        self._positions[order.symbol] = self._positions.get(order.symbol, 0) + sign * order.quantity
        self._cash -= commission
        order.status = OrderStatus.FILLED
        self._filled_ids.add(order.order_id)
        self._pending_orders.remove(order)
        logger.debug(f"Fill: {order.side.value} {order.quantity} {order.symbol} @ {fill_price:.2f}")

    def _realise(self, symbol: str, signed_qty: int, price: float) -> None:
        """Book a fill against the open position: the part that closes it pays its profit
        or loss into cash, the part that opens or adds to it moves the average entry.
        Cash used to take only commissions, so a closed trade's result vanished from
        every equity curve (2026-11-22)."""
        pos = self._positions.get(symbol, 0)
        avg = self._avg_price.get(symbol, price)
        if pos and (pos > 0) != (signed_qty > 0):                  # reduces or flips the position
            closed = min(abs(pos), abs(signed_qty))
            direction = 1 if pos > 0 else -1
            self._cash += (price - avg) * closed * direction * self._point_value
            left = pos + signed_qty
            if left == 0:
                self._avg_price.pop(symbol, None)
            elif (left > 0) != (pos > 0):                          # flipped: the rest opens at this price
                self._avg_price[symbol] = price
        else:                                                      # opens or adds
            new = pos + signed_qty
            self._avg_price[symbol] = (avg * abs(pos) + price * abs(signed_qty)) / abs(new)

    def _get_fill_price(self, order: Order, o: float, h: float, l: float, c: float) -> float | None:
        """Where a bar fills this order, or None. A gap fills at the open, not at the
        order's price: a stop gapped through could not have been filled at its level,
        and a limit gapped through got the better open. A limit never fills worse than
        its limit, so no slippage is added to it."""
        slippage = self._slippage_ticks * self._tick_size
        buy = order.side == OrderSide.BUY

        if order.order_type == OrderType.MARKET:
            return o + slippage if buy else o - slippage

        if order.order_type == OrderType.STOP:
            if buy and h >= order.stop_price:
                return max(order.stop_price, o) + slippage
            if not buy and l <= order.stop_price:
                return min(order.stop_price, o) - slippage
            return None

        if order.order_type == OrderType.STOP_LIMIT and not order.triggered:
            if buy and h >= order.stop_price:
                order.triggered = True
                at = max(order.stop_price, o)              # where the stop was reached
                return at if at <= order.limit_price else None
            if not buy and l <= order.stop_price:
                order.triggered = True
                at = min(order.stop_price, o)
                return at if at >= order.limit_price else None
            return None

        # LIMIT, or a STOP_LIMIT already triggered on an earlier bar
        if buy and l <= order.limit_price:
            return min(order.limit_price, o)
        if not buy and h >= order.limit_price:
            return max(order.limit_price, o)
        return None

    @property
    def tick_size(self) -> float:
        return self._tick_size

    @property
    def initial_capital(self) -> float:
        return self._initial_capital
