"""
The live chart and the exported HTML report must never show different oscillator
values for the same backtest.

They are drawn by separate code: the chart plots what api/serializers.py sends,
and the report builds its own Plotly figure in api/report/report.py. A change
made to one and not the other has already shipped once, so this compares the
two directly -- the value the chart is sent for every bar against the value the
report's figure actually plots for that bar, read out of the figure's traces.
"""

import math
from datetime import datetime

import pytest

from src.data.sample_data import generate_sample_data
from src.data.csv_provider import CSVDataProvider
from src.strategies import MACrossoverStrategy
from src.backtesting.engine import BacktestEngine
from api.serializers import price_data_to_response
from api.report.report import _candlestick_chart


@pytest.fixture(scope="module")
def results():
    symbol = "ESOSCPARITY"
    generate_sample_data(
        symbol=symbol, start=datetime(2024, 1, 2, 9, 30),
        bars=900, timeframe_minutes=5, base_price=4500.0,
        tick_size=0.25, seed=11, save_dir="data/historical",
    )
    engine = BacktestEngine(
        data_provider=CSVDataProvider("data/historical"),
        strategy=MACrossoverStrategy(fast=9, slow=21),
        symbol=symbol, timeframe="5m",
        initial_capital=100_000.0,
        tick_size=0.25, tick_value=12.50, point_value=50.0,
    )
    return engine.run(datetime(2024, 1, 2), datetime(2024, 12, 31))


@pytest.fixture(scope="module")
def live(results):
    return price_data_to_response(results.price_data)["indicators"]


@pytest.fixture(scope="module")
def report_fig(results):
    return _candlestick_chart(results)


def _report_trace(fig, name):
    traces = [t for t in fig.data if t.name == name]
    assert len(traces) == 1, f"report figure has {len(traces)} traces named {name!r}"
    return list(traces[0].y)


def _empty(v):
    return v is None or (isinstance(v, float) and math.isnan(v))


@pytest.mark.parametrize("report_name,api_key", [
    ("RSI(2)", "rsi2"),
    ("FullK", "stochrsi_k"),
    ("FullD", "stochrsi_d"),
    ("RSI(13)", "rsi13"),
    ("MoneyFlowIndex", "mfi"),
])
def test_report_plots_exactly_what_the_chart_is_sent(live, report_fig, report_name, api_key):
    chart = live[api_key]
    report = _report_trace(report_fig, report_name)
    assert len(chart) == len(report), f"{report_name}: {len(chart)} chart bars vs {len(report)} report bars"
    compared = 0
    for i, (a, b) in enumerate(zip(chart, report)):
        assert _empty(a) == _empty(b), f"{report_name} bar {i}: empty on one side only ({a!r} vs {b!r})"
        if not _empty(a):
            assert abs(a - b) < 1e-9, f"{report_name} bar {i}: chart {a} vs report {b}"
            compared += 1
    assert compared > 100, f"{report_name}: only {compared} populated bars compared -- fixture too short"


def test_the_price_stochastic_is_gone_from_both(live, report_fig):
    assert "stoch_k" not in live and "stoch_d" not in live
    names = {t.name for t in report_fig.data}
    assert not ({"%K", "%D"} & names), f"report still draws the price Stochastic: {names & {'%K', '%D'}}"


def test_mfi_levels_are_80_20_in_the_report(report_fig):
    levels = sorted(s.y0 for s in report_fig.layout.shapes
                    if s.type == "line" and s.yref in ("y5", "y5 domain") and s.y0 == s.y1)
    assert levels == [20, 80], levels


def test_without_volume_neither_the_chart_nor_the_report_draws_mfi(results):
    import copy
    bare = copy.copy(results)
    bare.price_data = results.price_data.drop(columns=["volume"])
    chart = price_data_to_response(bare.price_data)["indicators"]["mfi"]
    assert chart and all(v is None for v in chart), "chart is sent MFI values without volume"
    fig = _candlestick_chart(bare)
    assert not [t for t in fig.data if t.name == "MoneyFlowIndex"], "report draws MFI without volume"


def test_stochrsi_levels_are_80_20_in_the_report(report_fig):
    # Row 3 is StochRSI; its reference lines are the report's y3 horizontal lines.
    levels = sorted(s.y0 for s in report_fig.layout.shapes
                    if s.type == "line" and s.yref in ("y3", "y3 domain") and s.y0 == s.y1)
    assert levels == [20, 80], levels
