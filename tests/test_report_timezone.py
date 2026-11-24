"""Export Report prints its times in the sidebar's "Times in" zone (2026-11-24).

The report was always Eastern while sir's app shows Central, so every time in
it read an hour off his chart. Everything is still worked out on Eastern bars;
only the printed clock moves -- as the live chart does (ZonedCandlestickChart).
"""

import base64
import json
import re
from datetime import datetime, timedelta

import numpy as np
import plotly.graph_objects as go
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.report.report import shift_figure_times


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def backtest_id(client):
    r = client.post("/api/backtests", json={
        "symbol": "ES", "strategy_id": "ma_crossover", "timeframe": "5m",
        "start_date": "2024-01-01", "end_date": "2024-01-10", "data_source": "synthetic",
        "initial_capital": 100000, "params": {"fast": 9, "slow": 21},
    })
    assert r.status_code == 200, r.text
    return r.json()["backtest_id"]


def _report(client, backtest_id, fmt="html", **extra):
    r = client.get(f"/api/backtests/{backtest_id}/report", params={"format": fmt, **extra})
    assert r.status_code == 200, r.text[:300]
    return r


def _trade_times(html):
    return re.findall(r"<td class='dir-(?:long|short)'>\w+</td><td>([\d-]+ [\d:]+)</td>", html)


def _candle_x(html):
    """The candlestick trace's x values, as the page's Plotly JSON carries them."""
    m = re.search(r'"type":\s*"candlestick"', html)
    assert m, "no candlestick trace"
    start = html.rfind("{", 0, m.start())
    x = json.loads(re.search(r'"x":\s*(\[[^\]]*\]|\{[^}]*\})', html[start:]).group(1))
    if isinstance(x, dict):                      # plotly's base64 array encoding
        return np.frombuffer(base64.b64decode(x["bdata"]), dtype=x["dtype"])
    return x


def test_central_moves_every_printed_time_back_an_hour(client, backtest_id):
    et, ct = _report(client, backtest_id).text, _report(client, backtest_id, tz_offset=-60).text
    et_t, ct_t = _trade_times(et), _trade_times(ct)
    assert et_t and len(et_t) == len(ct_t)
    fmt = "%Y-%m-%d %H:%M"
    assert all(datetime.strptime(c, fmt) == datetime.strptime(e, fmt) - timedelta(hours=1)
               for e, c in zip(et_t, ct_t))
    et_x, ct_x = _candle_x(et), _candle_x(ct)
    assert len(et_x) == len(ct_x)
    for e, c in ((et_x[0], ct_x[0]), (et_x[-1], ct_x[-1])):
        assert datetime.fromisoformat(str(c)) == datetime.fromisoformat(str(e)) - timedelta(hours=1)
    assert "Times in CT" in ct and "Times in ET" in et


def test_default_is_eastern_and_unchanged(client, backtest_id):
    assert _trade_times(_report(client, backtest_id).text) == _trade_times(
        _report(client, backtest_id, tz_offset=0).text)


def test_unknown_zone_is_refused(client, backtest_id):
    r = client.get(f"/api/backtests/{backtest_id}/report", params={"format": "html", "tz_offset": 30})
    assert r.status_code == 400


def test_trade_log_files_move_too(client, backtest_id):
    et = _report(client, backtest_id, "csv").text.splitlines()
    ct = _report(client, backtest_id, "csv", tz_offset=-60).text.splitlines()
    head = next(i for i, line in enumerate(et) if line.startswith("#,Direction"))
    e, c = et[head + 1].split(","), ct[head + 1].split(",")
    assert datetime.fromisoformat(c[2]) == datetime.fromisoformat(e[2]) - timedelta(hours=1)


def test_shift_figure_times_moves_x_shapes_annotations_and_breaks():
    t = [datetime(2026, 11, 16, 9, 30), datetime(2026, 11, 16, 9, 35)]
    fig = go.Figure(go.Scatter(x=t, y=[1, 2]))
    fig.add_trace(go.Bar(x=["Jan", "Feb"], y=[1, 2]))                 # not times: untouched
    fig.add_shape(type="line", x0=t[0], x1=t[1], y0=0, y1=1)
    fig.add_annotation(x=t[1], y=1, text="a")
    fig.update_layout(xaxis=dict(range=t, rangebreaks=[{"bounds": [t[0], t[1]]}]))
    shift_figure_times(fig, -60)
    hour = timedelta(hours=1)
    assert [v - hour for v in t] == [x for x in fig.data[0].x]
    assert list(fig.data[1].x) == ["Jan", "Feb"]
    assert fig.layout.shapes[0].x0 == t[0] - hour and fig.layout.annotations[0].x == t[1] - hour
    assert list(fig.layout.xaxis.range) == [v - hour for v in t]
    assert list(fig.layout.xaxis.rangebreaks[0].bounds) == [v - hour for v in t]
