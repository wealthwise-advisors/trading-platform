"""The rails every live order has to pass before it can reach a broker.

WHY THIS IS A SEPARATE MODULE, AND WHY IT IS FIRST.

Everything else in live trading is recoverable. A chart that draws wrong gets
fixed and redrawn; an order that goes to an exchange is money, and there is no
redraw. So the checks live here rather than inside the broker: a guard that
the thing it guards can edit is not a guard, and putting them in one small
file with no broker imports means they can be read in full, in one sitting, by
someone deciding whether to trust this with an account.

WHAT IT DOES NOT DO. It does not decide whether a trade is a good idea -- that
is the strategy's job. It refuses orders that are malformed, oversized, or
arriving faster than a human could have meant, which are the three ways an
automated system loses money without anyone intending it to.

Every refusal raises. Nothing here returns a "cleaned up" order: silently
correcting a quantity you did not ask for is how a system ends up trading a
size nobody chose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .base_broker import Order, OrderSide, OrderType


class OrderRejected(Exception):
    """An order failed a safety check and was not sent anywhere."""


@dataclass
class GuardLimits:
    """The ceilings. Deliberately low by default.

    A default that is safe but annoying gets raised on purpose by someone who
    has thought about it. A default that is generous gets discovered after the
    fill.
    """

    #: Contracts in any single order.
    max_contracts_per_order: int = 1
    #: Net position, long or short, across all orders for one symbol.
    max_position_contracts: int = 2
    #: Orders accepted in one session, counting rejections that got this far.
    max_orders_per_session: int = 20
    #: The soonest a second order may follow the first. A strategy that fires
    #: twice on one bar is a bug, and this is what stops the bug costing money.
    min_seconds_between_orders: float = 2.0
    #: Only these symbols may be traded. Empty means "none", not "all" --
    #: an unset allow-list must fail closed.
    allowed_symbols: frozenset[str] = frozenset()


@dataclass
class OrderGuard:
    """Stateful across a session: counts, timings and the kill switch."""

    limits: GuardLimits = field(default_factory=GuardLimits)
    _count: int = field(default=0, init=False)
    _last_at: datetime | None = field(default=None, init=False)
    _halted_reason: str | None = field(default=None, init=False)

    # ── the kill switch ───────────────────────────────────────────────────
    def halt(self, reason: str) -> None:
        """Stop accepting orders for the rest of the session.

        One way only, on purpose. Resuming means creating a new guard, which
        means going through whatever starts a session -- there is no button
        that un-halts a system that has already done something unexpected.
        """
        self._halted_reason = reason or "halted"

    @property
    def halted(self) -> bool:
        return self._halted_reason is not None

    @property
    def halt_reason(self) -> str | None:
        return self._halted_reason

    # ── the check ─────────────────────────────────────────────────────────
    def check(self, order: Order, *, current_position: int, now: datetime | None = None) -> None:
        """Raise OrderRejected unless this order is safe to send.

        `current_position` is the broker's own view of the net position in
        this symbol, passed in rather than remembered here: the guard must
        judge against what the ACCOUNT holds, not against what it believes it
        sent. Those two disagree exactly when something has gone wrong, which
        is the moment the check matters most.
        """
        now = now or datetime.now()

        if self.halted:
            raise OrderRejected(f"trading is halted: {self._halted_reason}")

        # ── the order itself ──
        if order.quantity <= 0:
            raise OrderRejected(f"quantity must be positive, got {order.quantity}")
        if order.quantity > self.limits.max_contracts_per_order:
            raise OrderRejected(
                f"{order.quantity} contracts exceeds the per-order limit of "
                f"{self.limits.max_contracts_per_order}")
        if not order.symbol or not order.symbol.strip():
            raise OrderRejected("order has no symbol")
        if order.symbol not in self.limits.allowed_symbols:
            # Fails closed: an empty allow-list refuses everything.
            raise OrderRejected(
                f"{order.symbol!r} is not in the allowed symbols "
                f"{sorted(self.limits.allowed_symbols) or '(none configured)'}")

        # A limit order with no limit is a market order wearing a disguise,
        # and it is the kind of typo that fills at a price nobody chose.
        if order.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT) and order.limit_price is None:
            raise OrderRejected(f"{order.order_type.value} order has no limit price")
        if order.order_type in (OrderType.STOP, OrderType.STOP_LIMIT) and order.stop_price is None:
            raise OrderRejected(f"{order.order_type.value} order has no stop price")
        for name, price in (("limit", order.limit_price), ("stop", order.stop_price)):
            if price is not None and not (price > 0):
                raise OrderRejected(f"{name} price must be positive, got {price}")

        # ── the session ──
        if self._count >= self.limits.max_orders_per_session:
            raise OrderRejected(
                f"session order limit reached ({self.limits.max_orders_per_session})")
        if self._last_at is not None:
            gap = (now - self._last_at).total_seconds()
            if gap < self.limits.min_seconds_between_orders:
                raise OrderRejected(
                    f"only {gap:.2f}s since the last order; the minimum is "
                    f"{self.limits.min_seconds_between_orders}s")

        # ── the resulting position ──
        delta = order.quantity if order.side is OrderSide.BUY else -order.quantity
        resulting = current_position + delta
        if abs(resulting) > self.limits.max_position_contracts:
            raise OrderRejected(
                f"would take the {order.symbol} position to {resulting:+d}, beyond the "
                f"limit of +/-{self.limits.max_position_contracts}")

    def record(self, now: datetime | None = None) -> None:
        """Note that an order was actually sent. Called only after a send."""
        self._count += 1
        self._last_at = now or datetime.now()

    @property
    def orders_sent(self) -> int:
        return self._count

    @property
    def orders_remaining(self) -> int:
        return max(0, self.limits.max_orders_per_session - self._count)
