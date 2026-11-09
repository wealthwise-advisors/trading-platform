"""VolumeAvg: sir's buyer/seller formula, its history, and the exported report."""

from datetime import datetime
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.main import app
from api.report.report import _candlestick_chart
from api.schemas.chart_settings import ChartSettings
from src.analysis.indicators import calc_volume_avg, calc_volume_split
from src.backtesting.engine import BacktestEngine

client = TestClient(app)


def _series(values, start="2026-11-09 09:30", freq="1min"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq=freq), dtype=float)


def _df(n=60):
    idx = pd.date_range("2026-11-09 09:30", periods=n, freq="1min")
    close = 100 + np.sin(np.arange(n) / 3)
    return pd.DataFrame({"open": close, "high": close + 1, "low": close - 1, "close": close,
                         "volume": np.arange(n, dtype=float) + 100}, index=idx)


def test_the_average_is_a_simple_mean_once_the_window_is_full():
    out = calc_volume_avg(_series([1, 2, 3, 4]), 3)
    assert out.isna().tolist() == [True, True, False, False]
    assert out.iloc[2:].tolist() == [2.0, 3.0]


def test_context_fills_the_first_bars_and_the_session_gap():
    context = _series([10, 20], start="2026-11-09 09:28")
    assert calc_volume_avg(_series([30, 40]), 3, context).tolist() == [20.0, 30.0]


@pytest.mark.parametrize("h,l,c,v,buyers,sellers", [
    (105, 100, 104, 1_500_000, 1_200_000, 300_000),   # sir's worked example
    (7568.75, 7567, 7567.25, 1959, 280, 1679),        # thinkorswim, 11:45
    (7576, 7573.25, 7574, 1925, 525, 1400),           # 11:34
    (7575.75, 7572, 7575.5, 2606, 2432, 174),         # 11:33
    (10, 10, 10, 100, 50, 50),                        # no range
])
def test_the_split(h, l, c, v, buyers, sellers):
    _, b, s = calc_volume_split(*[pd.Series([x], dtype=float) for x in (h, l, c, v)])
    assert (b.iloc[0], s.iloc[0]) == (buyers, sellers)


class _Provider:
    """Answers any range with the bars inside it."""

    def __init__(self, df):
        self.df = df

    def load(self, symbol, start, end, timeframe):
        return self.df[(self.df.index >= start) & (self.df.index <= end)]


def _context(df, kept, start, provider=None):
    engine = BacktestEngine.__new__(BacktestEngine)
    engine.data_provider = provider or _Provider(df)
    engine.symbol, engine.timeframe = "ES", "1m"
    return engine._volume_context(df, kept, start)


def test_context_holds_earlier_bars_and_bars_outside_the_session():
    df = _df(30)
    start = df.index[10].to_pydatetime()
    in_range = df[df.index >= start]
    kept = in_range.iloc[5:]
    ctx = _context(in_range, kept, start, _Provider(df))
    assert list(ctx.index) == list(df.index[:15])
    assert not ctx.index.isin(kept.index).any()


def test_a_provider_that_ignores_the_dates_cannot_duplicate_bars():
    df = _df(30)
    class Sloppy:
        def load(self, *a):
            return df
    assert _context(df, df, df.index[0].to_pydatetime(), Sloppy()).empty


def test_no_earlier_history_is_not_an_error():
    df = _df(30)
    class Failing:
        def load(self, *a):
            raise ValueError("no bars")
    assert _context(df, df, df.index[0].to_pydatetime(), Failing()).empty


def test_no_volume_column_means_no_context():
    assert _context(_df(5).drop(columns="volume"), _df(5), datetime(2026, 11, 9)).empty


def test_price_data_carries_the_volumes_the_session_filter_removed():
    r = client.post("/api/backtests", json={
        "symbol": "ES", "timeframe": "1m", "data_source": "synthetic", "strategy_id": "rsi_divergence",
        "params": {"rsi_overbought": 94, "rsi_oversold": 2, "swing_lookback": 5},
        "start_date": "2026-11-06", "end_date": "2026-11-09",
        "session_start": "10:00:00", "session_end": "11:00:00",
    })
    assert r.status_code == 200, r.text[:300]
    body = client.get(f"/api/backtests/{r.json()['backtest_id']}/price-data").json()
    ctx = body["volume_context"]
    assert ctx["t"] and len(ctx["t"]) == len(ctx["v"])
    assert not set(ctx["t"]) & {b["t"] for b in body["bars"]}


def _fig(chart=None, df=None, context=None):
    results = SimpleNamespace(price_data=_df() if df is None else df, trades=[], symbol="ES",
                              strategy_name="probe", volume_context=context)
    return _candlestick_chart(results, chart_settings=None if chart is None else ChartSettings.model_validate(chart))


def _named(fig, name):
    return [t for t in fig.data if t.name == name]


def test_the_report_draws_volume_avg_as_the_bottom_row_by_default():
    fig = _fig()
    bars, line = _named(fig, "Vol"), _named(fig, "VolAvg")
    assert bars and line and bars[0].yaxis == line[0].yaxis == "y5"
    assert fig.layout.yaxis5.title.text == "VolumeAvg (20)"


def test_the_report_uses_the_charts_length_and_context():
    context = _series([1000.0] * 3, start="2026-11-09 09:27")
    avg = _named(_fig({"volumeAvg": {"on": True, "length": 4}}, context=context), "VolAvg")[0].y
    assert avg[0] == pytest.approx((3000 + 100) / 4)


def test_the_report_leaves_it_out_when_off_or_without_volume():
    assert not _named(_fig({"volumeAvg": {"on": False, "length": 20}}), "Vol")
    assert not _named(_fig(df=_df().drop(columns="volume")), "Vol")


@pytest.mark.parametrize("length", [0, 501, -1])
def test_a_length_the_chart_could_not_send_is_refused(length):
    with pytest.raises(ValidationError):
        ChartSettings.model_validate({"volumeAvg": {"on": True, "length": length}})


def test_context_survives_the_database(tmp_path, monkeypatch):
    from datetime import time

    from db import backtests as bt_repo
    from db import connection
    from db import users as repo
    from tests._isolation_helpers import tiny_results

    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "volume.db")
    monkeypatch.setattr(bt_repo, "BLOB_DIR", tmp_path / "blobs")
    uid = repo.create_user("vol", "!", full_name="Vol", email="vol@example.com", country="IN", has_password=False)
    results = tiny_results()
    results.volume_context = _series([5.0, 6.0])
    bt_repo.insert("bt1", results, "synthetic", time(9, 30), time(16, 0), user_id=uid)
    loaded = bt_repo.fetch("bt1", uid)[0].volume_context
    assert loaded.tolist() == [5.0, 6.0]
    assert list(loaded.index) == list(results.volume_context.index)
