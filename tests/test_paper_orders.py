"""Paper orders (upgrade plan, Feature 5): honest fills for every order type, OCO,
brackets and trailing stops, against hand-built bars.

The rule throughout: when a bar cannot say which price came first, assume the one
worse for the trader. Paper results must never look better than reality.
"""
from datetime import datetime, timedelta

from src.broker.base_broker import Order, OrderSide, OrderStatus, OrderType
from src.broker.paper_broker import PaperBroker

T0 = datetime(2026, 11, 23, 10, 0)
BUY, SELL = OrderSide.BUY, OrderSide.SELL


def broker(slip=0):
    return PaperBroker(initial_capital=100_000, commission_per_contract=0, slippage_ticks=slip,
                       tick_size=0.25, tick_value=12.5)


def bar(b, o, h, l, c, i=0):
    b.process_bar("ES", o, h, l, c, T0 + timedelta(minutes=i))


def order(side, kind=OrderType.MARKET, qty=1, **kw):
    return Order(symbol="ES", side=side, quantity=qty, order_type=kind, **kw)


def fills(b):
    return [(f.side.value, f.quantity, f.fill_price) for f in b.get_fills()]


# ── fixes to the existing types ─────────────────────────────────────────────

def test_a_limit_never_fills_worse_than_its_limit():
    b = broker(slip=1)
    b.submit_order(order(BUY, OrderType.LIMIT, limit_price=100.0))
    bar(b, 102, 103, 99.5, 101)
    assert fills(b) == [("BUY", 1, 100.0)]


def test_a_limit_gapped_through_fills_at_the_better_open():
    b = broker()
    b.submit_order(order(SELL, OrderType.LIMIT, limit_price=100.0))
    bar(b, 104, 105, 103, 104)
    assert fills(b) == [("SELL", 1, 104.0)]


def test_a_stop_gapped_through_fills_at_the_open_not_the_stop():
    b = broker(slip=1)
    b.submit_order(order(BUY, OrderType.STOP, stop_price=100.0))
    bar(b, 105, 106, 104, 105)
    assert fills(b) == [("BUY", 1, 105.25)]
    s = broker()
    s.submit_order(order(SELL, OrderType.STOP, stop_price=100.0))
    bar(s, 95, 96, 94, 95)
    assert fills(s) == [("SELL", 1, 95.0)]


# ── stop-limit ──────────────────────────────────────────────────────────────

def test_stop_limit_fills_when_triggered_and_the_limit_is_reachable():
    b = broker()
    b.submit_order(order(BUY, OrderType.STOP_LIMIT, stop_price=100.0, limit_price=100.5))
    bar(b, 99, 101, 98.75, 100.75)
    assert fills(b) == [("BUY", 1, 100.0)]


def test_stop_limit_gapped_past_its_limit_waits_as_a_limit():
    b = broker()
    o = order(BUY, OrderType.STOP_LIMIT, stop_price=100.0, limit_price=100.5)
    b.submit_order(o)
    bar(b, 102, 103, 101, 102)                   # triggered, but never back to 100.5
    assert fills(b) == [] and o.status == OrderStatus.OPEN
    bar(b, 101, 101.5, 100.25, 100.5, 1)         # comes back: fills at the limit or better
    assert fills(b) == [("BUY", 1, 100.5)]


def test_stop_limit_not_triggered_does_nothing():
    b = broker()
    b.submit_order(order(SELL, OrderType.STOP_LIMIT, stop_price=95.0, limit_price=94.5))
    bar(b, 99, 100, 96, 97)
    assert fills(b) == []


# ── OCO ─────────────────────────────────────────────────────────────────────

def test_one_fill_cancels_the_rest_of_its_group():
    b = broker()
    t = order(SELL, OrderType.LIMIT, limit_price=110.0, oco_group="g")
    s = order(SELL, OrderType.STOP, stop_price=95.0, oco_group="g")
    b.submit_order(t)
    b.submit_order(s)
    bar(b, 100, 111, 99, 110)
    assert fills(b) == [("SELL", 1, 110.0)]
    assert s.status == OrderStatus.CANCELLED and b.working_orders() == []


def test_both_legs_inside_one_bar_the_stop_fills_first():
    b = broker()
    b.submit_order(order(SELL, OrderType.LIMIT, limit_price=110.0, oco_group="g"))
    b.submit_order(order(SELL, OrderType.STOP, stop_price=95.0, oco_group="g"))
    bar(b, 100, 111, 94, 100)
    assert fills(b) == [("SELL", 1, 95.0)]


# ── brackets ────────────────────────────────────────────────────────────────

def test_a_bracket_waits_for_its_entry_then_protects_it():
    b = broker()
    entry = order(BUY, OrderType.LIMIT, limit_price=100.0)
    tgt = order(SELL, OrderType.LIMIT, limit_price=104.0, parent_id=entry.order_id, oco_group="b1")
    stp = order(SELL, OrderType.STOP, stop_price=98.0, parent_id=entry.order_id, oco_group="b1")
    for o in (entry, tgt, stp):
        b.submit_order(o)
    bar(b, 103, 105, 101, 104)                   # target price, but no entry yet: nothing
    assert fills(b) == []
    bar(b, 101, 101, 99.5, 100.5, 1)             # entry fills
    assert fills(b) == [("BUY", 1, 100.0)] and b.get_position("ES") == 1
    bar(b, 101, 104.5, 100.5, 104, 2)            # target
    assert fills(b)[-1] == ("SELL", 1, 104.0) and b.get_position("ES") == 0
    assert stp.status == OrderStatus.CANCELLED


def test_cancelling_an_entry_cancels_its_bracket():
    b = broker()
    entry = order(BUY, OrderType.LIMIT, limit_price=100.0)
    child = order(SELL, OrderType.STOP, stop_price=98.0, parent_id=entry.order_id)
    b.submit_order(entry)
    b.submit_order(child)
    assert b.cancel_order(entry.order_id)
    assert child.status == OrderStatus.CANCELLED and b.working_orders() == []


def test_the_entry_bar_can_stop_out_but_not_reach_the_target():
    """Inside the entry's own bar the order of prices is unknown: the stop may count,
    the target may not (the cautious assumption)."""
    b = broker()
    entry = order(BUY)
    b.submit_order(entry)
    b.submit_order(order(SELL, OrderType.LIMIT, limit_price=104.0, parent_id=entry.order_id, oco_group="b"))
    b.submit_order(order(SELL, OrderType.STOP, stop_price=98.0, parent_id=entry.order_id, oco_group="b"))
    bar(b, 100, 105, 97, 101)
    assert fills(b) == [("BUY", 1, 100.0), ("SELL", 1, 98.0)]


# ── trailing stops ──────────────────────────────────────────────────────────

def test_a_trailing_stop_ratchets_and_never_backs_off():
    b = broker()
    b.submit_order(order(BUY))
    bar(b, 100, 100, 100, 100)
    trail = order(SELL, OrderType.STOP, stop_price=98.0, trail_ticks=8)     # 2 points behind the high
    b.submit_order(trail)
    bar(b, 100, 103, 100.5, 102.5, 1)
    assert trail.stop_price == 101.0
    bar(b, 102.5, 102.75, 101.25, 101.5, 2)        # lower high: the stop stays
    assert trail.stop_price == 101.0 and b.get_position("ES") == 1
    bar(b, 101.5, 101.75, 100.0, 100.25, 3)
    assert fills(b)[-1] == ("SELL", 1, 101.0) and b.get_position("ES") == 0


def test_a_trailing_stop_moves_after_the_bar_is_checked():
    """It is checked at the stop it had when the bar opened: moving it up by this bar's
    high first would stop out on a low that may have come before that high."""
    b = broker()
    b.submit_order(order(SELL))
    bar(b, 100, 100, 100, 100)
    trail = order(BUY, OrderType.STOP, stop_price=103.0, trail_ticks=8)
    b.submit_order(trail)
    bar(b, 100, 102.5, 97, 98, 1)                  # low 97 -> stop would be 99, high 102.5 is under 103
    assert b.get_position("ES") == -1 and trail.stop_price == 99.0


def test_working_orders_lists_open_ones_only():
    b = broker()
    a = order(BUY, OrderType.LIMIT, limit_price=90.0)
    b.submit_order(a)
    b.submit_order(order(BUY))
    bar(b, 100, 100, 99, 100)
    assert [o.order_id for o in b.working_orders()] == [a.order_id]
