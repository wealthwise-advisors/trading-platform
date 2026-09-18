"""The rails that stand between a strategy and a real account.

These are the tests that matter most in the repository. Everything else here
protects a number on a screen; these protect money, and each one is a way an
automated trader loses it without anyone deciding to.
"""

from datetime import datetime, timedelta

import pytest

from src.broker.base_broker import Order, OrderSide, OrderType
from src.broker.order_guard import GuardLimits, OrderGuard, OrderRejected

T0 = datetime(2026, 9, 18, 10, 0, 0)


def _guard(**kw) -> OrderGuard:
    limits = GuardLimits(allowed_symbols=frozenset({"ES"}), **kw)
    return OrderGuard(limits=limits)


def _order(qty=1, side=OrderSide.BUY, symbol="ES", **kw) -> Order:
    return Order(symbol=symbol, side=side, quantity=qty, **kw)


# ── the allow-list fails closed ───────────────────────────────────────────
def test_an_unconfigured_allow_list_refuses_everything():
    """The dangerous default is "allow all". An empty list means none."""
    bare = OrderGuard()
    with pytest.raises(OrderRejected, match="not in the allowed symbols"):
        bare.check(_order(), current_position=0, now=T0)


def test_a_symbol_outside_the_allow_list_is_refused():
    with pytest.raises(OrderRejected, match="NQ"):
        _guard().check(_order(symbol="NQ"), current_position=0, now=T0)


# ── size ──────────────────────────────────────────────────────────────────
def test_a_quantity_over_the_per_order_limit_is_refused():
    with pytest.raises(OrderRejected, match="per-order limit"):
        _guard(max_contracts_per_order=1).check(_order(qty=2), current_position=0, now=T0)


@pytest.mark.parametrize("qty", [0, -1])
def test_a_nonsense_quantity_is_refused(qty):
    with pytest.raises(OrderRejected, match="quantity must be positive"):
        _guard().check(_order(qty=qty), current_position=0, now=T0)


def test_the_position_limit_counts_the_RESULTING_position():
    """One contract at a time is still a runaway if nothing watches the total."""
    g = _guard(max_position_contracts=2)
    g.check(_order(qty=1), current_position=1, now=T0)          # -> +2, allowed
    with pytest.raises(OrderRejected, match=r"\+3"):
        g.check(_order(qty=1), current_position=2, now=T0)      # -> +3, refused


def test_the_position_limit_is_symmetric_for_shorts():
    with pytest.raises(OrderRejected, match="-3"):
        _guard(max_position_contracts=2).check(
            _order(side=OrderSide.SELL), current_position=-2, now=T0)


def test_selling_out_of_a_long_is_allowed_even_at_the_limit():
    """The limit must never trap a position it let you open."""
    _guard(max_position_contracts=2).check(
        _order(side=OrderSide.SELL), current_position=2, now=T0)


def test_the_position_comes_from_the_ACCOUNT_not_from_memory():
    """Passed in per call, so a guard that has lost track of what it sent
    still judges against what is really held."""
    g = _guard(max_position_contracts=2)
    with pytest.raises(OrderRejected):
        g.check(_order(), current_position=99, now=T0)


# ── malformed orders ──────────────────────────────────────────────────────
def test_a_limit_order_without_a_limit_price_is_refused():
    with pytest.raises(OrderRejected, match="no limit price"):
        _guard().check(_order(order_type=OrderType.LIMIT), current_position=0, now=T0)


def test_a_stop_order_without_a_stop_price_is_refused():
    with pytest.raises(OrderRejected, match="no stop price"):
        _guard().check(_order(order_type=OrderType.STOP), current_position=0, now=T0)


def test_a_nonpositive_price_is_refused():
    with pytest.raises(OrderRejected, match="limit price must be positive"):
        _guard().check(_order(order_type=OrderType.LIMIT, limit_price=0.0),
                       current_position=0, now=T0)


# ── rate and volume ───────────────────────────────────────────────────────
def test_two_orders_in_the_same_instant_are_refused():
    """A strategy firing twice on one bar is a bug; this is what stops the bug
    costing money."""
    g = _guard(min_seconds_between_orders=2.0)
    g.check(_order(), current_position=0, now=T0)
    g.record(now=T0)
    with pytest.raises(OrderRejected, match="since the last order"):
        g.check(_order(), current_position=0, now=T0)


def test_an_order_after_the_cool_off_is_allowed():
    g = _guard(min_seconds_between_orders=2.0)
    g.check(_order(), current_position=0, now=T0)
    g.record(now=T0)
    g.check(_order(), current_position=0, now=T0 + timedelta(seconds=2))


def test_the_session_order_cap_is_enforced():
    g = _guard(max_orders_per_session=2, min_seconds_between_orders=0)
    for i in range(2):
        t = T0 + timedelta(seconds=i)
        g.check(_order(), current_position=0, now=t)
        g.record(now=t)
    with pytest.raises(OrderRejected, match="session order limit"):
        g.check(_order(), current_position=0, now=T0 + timedelta(seconds=9))


def test_only_a_SENT_order_counts_towards_the_session_cap():
    """check() alone must not consume budget, or a rejected order would eat
    into the allowance for good ones."""
    g = _guard(max_orders_per_session=1, min_seconds_between_orders=0)
    g.check(_order(), current_position=0, now=T0)
    g.check(_order(), current_position=0, now=T0)
    assert g.orders_sent == 0
    assert g.orders_remaining == 1


# ── the kill switch ───────────────────────────────────────────────────────
def test_halting_refuses_everything_afterwards():
    g = _guard()
    g.halt("bad fill price")
    with pytest.raises(OrderRejected, match="halted: bad fill price"):
        g.check(_order(), current_position=0, now=T0)


def test_a_halt_cannot_be_undone_from_the_guard():
    """There is no resume(). Coming back means a new session, deliberately --
    nothing should be able to un-halt a system that already surprised someone."""
    assert not hasattr(OrderGuard, "resume")
    assert not hasattr(OrderGuard, "unhalt")


def test_a_clean_order_passes():
    g = _guard()
    g.check(_order(), current_position=0, now=T0)
    assert not g.halted
