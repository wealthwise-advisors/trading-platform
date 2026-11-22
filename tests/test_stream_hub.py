"""The Schwab stream hub (upgrade plan, Feature 3): one server-side stream, bars in memory.

Messages are in the envelope Schwab actually sent (recorded 2026-11-22: LOGIN, SUBS,
LEVELONE_FUTURES snapshot keyed "/ES", heartbeats every 10 s). CHART_FUTURES content
follows Schwab's documented fields (0 key, 1 chart time ms, 2-5 OHLC, 6 volume).
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from src.data.stream_hub import StreamHub

ET = ZoneInfo("America/New_York")


def ms(et: str) -> int:
    """Epoch ms of an ET wall-clock time."""
    return int(datetime.fromisoformat(et).replace(tzinfo=ET).timestamp() * 1000)


def chart(minute: str, o, h, l, c, v, key="/ES"):
    return {"data": [{"service": "CHART_FUTURES", "timestamp": ms(minute), "command": "SUBS",
                      "content": [{"key": key, "seq": 1, "0": key, "1": ms(minute),
                                   "2": o, "3": h, "4": l, "5": c, "6": v}]}]}


def quote(at: str, last=None, total=None, key="/ES"):
    c = {"key": key, "delayed": False, "assetMainType": "FUTURE"}
    if last is not None:
        c["3"] = last
    if total is not None:
        c["8"] = total
    c["11"] = ms(at)
    return {"data": [{"service": "LEVELONE_FUTURES", "timestamp": ms(at), "command": "SUBS", "content": [c]}]}


HEARTBEAT = {"notify": [{"heartbeat": "1795339846033"}]}


@pytest.fixture
def hub():
    clock = {"now": datetime(2026, 11, 23, 10, 0, tzinfo=timezone.utc)}
    h = StreamHub(now=lambda: clock["now"])
    h.clock = clock
    h.connected = True
    h.seed("ES", pd.DataFrame({"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1.0]},
                              index=pd.DatetimeIndex([datetime(2026, 11, 23, 4, 0)], name="timestamp")))
    h.on_message(HEARTBEAT)
    return h


def test_a_chart_bar_is_kept_at_its_eastern_minute(hub):
    hub.on_message(chart("2026-11-23T04:58", 6900, 6902, 6899, 6901, 120))
    df = hub.bars_1m("ES", datetime(2026, 11, 23, 4, 58))
    assert list(df.index) == [pd.Timestamp("2026-11-23 04:58")]
    assert df.iloc[0].to_dict() == {"open": 6900, "high": 6902, "low": 6899, "close": 6901, "volume": 120}


def test_a_later_message_for_the_same_minute_replaces_it(hub):
    hub.on_message(chart("2026-11-23T04:58", 6900, 6902, 6899, 6901, 120))
    hub.on_message(chart("2026-11-23T04:58", 6900, 6903, 6899, 6903, 150))
    df = hub.bars_1m("ES", datetime(2026, 11, 23, 4, 58))
    assert len(df) == 1 and df.iloc[0]["close"] == 6903 and df.iloc[0]["volume"] == 150


def test_quotes_build_the_forming_minute_until_its_bar_arrives(hub):
    hub.on_message(chart("2026-11-23T04:58", 6900, 6902, 6899, 6901, 120))
    hub.on_message(quote("2026-11-23T04:59:05", last=6901.25, total=1000))
    hub.on_message(quote("2026-11-23T04:59:20", last=6904.0, total=1030))
    hub.on_message(quote("2026-11-23T04:59:40", last=6900.5, total=1045))
    df = hub.bars_1m("ES", datetime(2026, 11, 23, 4, 58))
    assert list(df.index) == [pd.Timestamp("2026-11-23 04:58"), pd.Timestamp("2026-11-23 04:59")]
    forming = df.iloc[1].to_dict()
    assert forming == {"open": 6901.25, "high": 6904.0, "low": 6900.5, "close": 6900.5, "volume": 45}
    hub.on_message(chart("2026-11-23T04:59", 6901, 6904, 6900.25, 6900.5, 50))   # the real bar wins
    assert hub.bars_1m("ES", datetime(2026, 11, 23, 4, 59)).iloc[0]["volume"] == 50


def test_a_quote_with_only_some_fields_uses_the_last_known_ones(hub):
    hub.on_message(quote("2026-11-23T05:00:01", last=6910.0, total=2000))
    hub.on_message(quote("2026-11-23T05:00:30", total=2010))          # volume moved, price did not
    hub.on_message(quote("2026-11-23T05:00:45", last=6911.0))
    bar = hub.bars_1m("ES", datetime(2026, 11, 23, 5, 0)).iloc[0].to_dict()
    assert bar == {"open": 6910.0, "high": 6911.0, "low": 6910.0, "close": 6911.0, "volume": 10}


def test_the_daily_volume_reset_never_makes_a_negative_bar(hub):
    hub.on_message(quote("2026-11-23T05:01:01", last=6910.0, total=900_000))
    hub.on_message(quote("2026-11-23T05:02:01", last=6911.0, total=12))   # new session: total restarted
    assert (hub.bars_1m("ES", datetime(2026, 11, 23, 5, 0))["volume"] >= 0).all()


def test_the_contract_key_maps_to_its_root(hub):
    hub.on_message(chart("2026-11-23T04:58", 1, 1, 1, 1, 1, key="/ESZ26"))
    assert len(hub.bars_1m("ES", datetime(2026, 11, 23, 4, 58))) == 1


def test_silent_for_30_seconds_means_not_streaming(hub):
    hub.on_message(chart("2026-11-23T04:58", 1, 1, 1, 1, 1))
    hub.clock["now"] += timedelta(seconds=31)
    assert hub.bars_1m("ES", datetime(2026, 11, 23, 4, 58)) is None


def test_bars_before_the_seed_are_not_claimed(hub):
    assert hub.bars_1m("ES", datetime(2026, 11, 23, 3, 0)) is None


def test_a_symbol_never_seeded_is_not_claimed(hub):
    assert hub.bars_1m("NQ", datetime(2026, 11, 23, 4, 58)) is None


def test_a_dropped_connection_forgets_coverage_until_seeded_again(hub):
    hub.on_message(chart("2026-11-23T04:58", 1, 1, 1, 1, 1))
    hub.disconnected("connection lost")
    hub.connected = True
    hub.on_message(HEARTBEAT)
    assert hub.bars_1m("ES", datetime(2026, 11, 23, 4, 58)) is None     # a gap may hide in the drop


def test_seed_bars_and_stream_bars_join(hub):
    hub.on_message(chart("2026-11-23T04:58", 6900, 6902, 6899, 6901, 120))
    df = hub.bars_1m("ES", datetime(2026, 11, 23, 4, 0))
    assert list(df.index) == [pd.Timestamp("2026-11-23 04:00"), pd.Timestamp("2026-11-23 04:58")]


def test_rubbish_is_ignored(hub):
    for junk in ["not json", {"data": [{"service": "CHART_FUTURES", "content": [{"key": "/ES"}]}]},
                 {"data": [{"service": "LEVELONE_FUTURES", "content": [{"key": "/ES", "3": "x"}]}]}, {}]:
        hub.on_message(junk)
    assert len(hub.bars_1m("ES", datetime(2026, 11, 23, 4, 0))) == 1


def test_nothing_to_seed_is_an_empty_start_not_a_crash(monkeypatch):
    """Weekend: Schwab's loader raises "No data returned" for an empty window. The hub
    used to die on it and log in again every few seconds."""
    from src.data import stream_hub as sh

    class NoBars:
        def load(self, *a):
            raise ValueError("No data returned from Schwab for /ES")
    df = sh._seed_bars(NoBars(), "ES")
    assert df.empty and list(df.columns) == ["open", "high", "low", "close", "volume"]
    h = StreamHub(now=lambda: datetime(2026, 11, 22, 10, 0, tzinfo=timezone.utc))
    h.connected = True
    h.seed("ES", df)
    h.on_message(HEARTBEAT)
    assert h.bars_1m("ES", datetime(2026, 11, 22, 5, 0)) is not None      # covered from now on
    assert h.bars_1m("ES", datetime(2026, 11, 22, 4, 0)) is None          # not before


def test_only_futures_are_streamed(monkeypatch):
    """CHART_FUTURES and LEVELONE_FUTURES carry futures only. A stock watched there would
    be seeded over REST, never updated, and the hub would freeze its chart."""
    monkeypatch.setenv("AUTOTRADER_STREAM", "1")
    h = StreamHub()
    started = []
    monkeypatch.setattr(h, "_run", lambda: started.append(1))
    h.watch("AAPL")
    assert "AAPL" not in h._roots and h._thread is None
    h.watch("es")
    assert "ES" in h._roots
