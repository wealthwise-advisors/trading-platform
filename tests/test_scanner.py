"""The futures scanner (upgrade plan, Feature 7): each condition on fixed bars, scan values
equal to the chart's, and a scan that survives a symbol without data."""
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api import serializers
from api.main import app
from src.analysis import scanner

client = TestClient(app)


def bars(closes, volumes=None, highs=None, lows=None):
    idx = pd.date_range("2026-11-20 09:30", periods=len(closes), freq="5min")
    c = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame({"open": c, "high": highs if highs is not None else c + 0.5,
                         "low": lows if lows is not None else c - 0.5, "close": c,
                         "volume": volumes if volumes is not None else [100.0] * len(c)}, index=idx)


def one(df, cond):
    return scanner.evaluate(df, [cond], "all")


def test_indicator_above_and_below():
    up = bars(np.linspace(100, 120, 40))
    assert one(up, {"kind": "indicator", "name": "rsi2", "op": "above", "value": 90})["matched"]
    assert not one(up, {"kind": "indicator", "name": "rsi2", "op": "below", "value": 10})["matched"]


def test_indicator_crossing_needs_the_previous_bar_on_the_other_side():
    closes = list(np.linspace(120, 100, 30)) + [104]                 # falling, then one bar up
    df = bars(closes)
    rsi = scanner.series_for(df)["rsi2"]
    assert rsi.iloc[-2] < 50 < rsi.iloc[-1]
    assert one(df, {"kind": "indicator", "name": "rsi2", "op": "crosses_above", "value": 50})["matched"]
    assert not one(df, {"kind": "indicator", "name": "rsi2", "op": "crosses_below", "value": 50})["matched"]


def test_price_change_over_n_bars():
    df = bars([100] * 10 + [102])
    r = one(df, {"kind": "change_pct", "bars": 5, "op": "above", "value": 1.5})
    assert r["matched"] and r["values"][0]["value"] == pytest.approx(2.0)


def test_unusual_volume_against_volume_avg():
    df = bars([100] * 25, volumes=[100.0] * 24 + [400.0])
    r = one(df, {"kind": "volume_vs_avg", "op": "above", "value": 2})
    assert r["matched"] and r["values"][0]["value"] > 2


def test_breakout_of_the_n_bar_high_and_low():
    df = bars([100] * 20 + [103])
    r = one(df, {"kind": "breakout", "bars": 10, "direction": "high"})
    assert r["matched"] and r["values"][0]["value"] == 100.5          # the 10-bar high it broke
    assert not one(df, {"kind": "breakout", "bars": 10, "direction": "low"})["matched"]


def test_vwap_band_position():
    closes = [100] * 30 + [130]
    vols = [1000.0] * 30 + [1.0]                                     # the spike barely moves VWAP
    df = bars(closes, volumes=vols)
    assert one(df, {"kind": "vwap", "position": "above_upper"})["matched"]
    assert not one(df, {"kind": "vwap", "position": "below_vwap"})["matched"]


def test_all_versus_any():
    df = bars([100] * 20 + [103])
    a = {"kind": "breakout", "bars": 10, "direction": "high"}
    b = {"kind": "breakout", "bars": 10, "direction": "low"}
    assert not scanner.evaluate(df, [a, b], "all")["matched"]
    assert scanner.evaluate(df, [a, b], "any")["matched"]


def test_too_few_bars_is_not_a_match_and_says_so():
    r = one(bars([100, 101]), {"kind": "change_pct", "bars": 5, "op": "above", "value": 0})
    assert not r["matched"] and r["values"][0]["value"] is None


def test_scan_values_equal_the_charts():
    df = bars(list(100 + np.sin(np.arange(80) / 4) * 3), volumes=list(100 + np.arange(80) * 3.0))
    chart = serializers.price_data_to_response(df, None, None)["indicators"]
    s = scanner.series_for(df)
    for name, key in (("rsi2", "rsi2"), ("rsi13", "rsi13"), ("stochrsi", "stochrsi_k"), ("mfi", "mfi")):
        assert s[name].iloc[-1] == pytest.approx(chart[key][-1]), name


# ── the endpoint ────────────────────────────────────────────────────────────

def test_scan_over_several_symbols_ranks_matches_first():
    r = client.post("/api/scan", json={
        "data_source": "synthetic", "timeframe": "5m", "symbols": ["ES", "NQ", "GC"], "combine": "all",
        "conditions": [{"kind": "indicator", "name": "rsi13", "op": "above", "value": 0}]})
    assert r.status_code == 200, r.text
    rows = r.json()["rows"]
    assert {x["symbol"] for x in rows} == {"ES", "NQ", "GC"}
    assert all(x["matched"] for x in rows)
    assert all(x["last"] is not None and x["bar_time"] for x in rows)


def test_a_symbol_without_data_is_reported_not_fatal(monkeypatch):
    from api.routers import backtests
    real = backtests._build_provider

    def build(source, symbol, *a, **k):
        if symbol == "NQ":
            raise ValueError("No data for NQ")
        return real(source, symbol, *a, **k)
    monkeypatch.setattr(backtests, "_build_provider", build)
    r = client.post("/api/scan", json={"data_source": "synthetic", "timeframe": "5m", "symbols": ["ES", "NQ"],
                                       "conditions": [{"kind": "breakout", "bars": 5, "direction": "high"}]})
    rows = {x["symbol"]: x for x in r.json()["rows"]}
    assert rows["NQ"]["error"] and not rows["NQ"]["matched"] and rows["ES"]["error"] is None


def test_the_request_budget_is_capped():
    r = client.post("/api/scan", json={"data_source": "synthetic", "timeframe": "5m",
                                       "symbols": [f"S{i}" for i in range(30)], "conditions": []})
    assert r.status_code == 422


def test_unknown_conditions_are_refused():
    r = client.post("/api/scan", json={"data_source": "synthetic", "timeframe": "5m", "symbols": ["ES"],
                                       "conditions": [{"kind": "astrology"}]})
    assert r.status_code == 422
