"""
Daily (1d) and weekly (1w) bars.

They are not two more bin widths. A daily bar is a whole trading session and a
weekly bar is five of them, so every place the app assumed intraday bars had to
be taught otherwise:

  * grouping -- by trading DATE, so CME Globex's Sunday-evening session is
    Monday's bar, not a Sunday bar and a one-day week
  * Schwab -- daily and weekly are native frequencies, fetched in one request
    with a year period rather than 30-day minute chunks
  * session hours -- a daily bar has no useful clock time; the filter would
    drop every one
  * synthetic data -- one bar per trading day or week, so a twenty-year range
    is actually filled
  * VWAP -- resets every session, so on bars that ARE sessions it is not sent
    or drawn
  * the time axis -- weekends are skipped for futures, not for crypto
  * Market Grid -- replays from 1-minute bars and does not offer them
"""

from datetime import date, datetime, time
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.deps import get_contract_spec
from api.main import app
from api.report.report import _candlestick_chart
from api.routers.backtests import _build_provider
from api.serializers import price_data_to_response
from src.analysis.indicators import compute_rangebreaks
from src.backtesting.engine import BacktestEngine
from src.data.resample import (
    ALL_TIMEFRAMES, BAR_DAYS, TF_MINUTES, bars_are_daily_or_longer, day_session_anchor,
    is_daily_or_longer, resample_ohlcv,
)
from src.data.schwab_provider import SchwabDataProvider, _fetch_plan, build_timeframe
from src.strategies import MACrossoverStrategy

client = TestClient(app)


def _bars(index: pd.DatetimeIndex) -> pd.DataFrame:
    df = pd.DataFrame({"open": np.arange(len(index)) * 0.01 + 5000.0}, index=index)
    df["high"] = df["open"] + 1.0
    df["low"] = df["open"] - 1.0
    df["close"] = df["open"] + 0.5
    df["volume"] = 1.0
    return df


@pytest.fixture(scope="module")
def globex_minutes() -> pd.DataFrame:
    """Two weeks of Globex: Sunday 18:00 ET to Friday 17:00 ET, halted 17:00-18:00 daily."""
    parts = []
    for sunday in (pd.Timestamp("2026-08-02 18:00"), pd.Timestamp("2026-08-09 18:00")):
        rng = pd.date_range(sunday, sunday + pd.Timedelta(days=4, hours=23), freq="1min", inclusive="left")
        parts.append(rng[rng.hour != 17])
    return _bars(parts[0].append(parts[1]))


@pytest.fixture(scope="module")
def equity_minutes() -> pd.DataFrame:
    """One week of 09:30-16:00 ET equity minutes."""
    days = pd.bdate_range("2026-08-03", "2026-08-07")
    idx = pd.DatetimeIndex([])
    for d in days:
        idx = idx.append(pd.date_range(d + pd.Timedelta(hours=9, minutes=30), d + pd.Timedelta(hours=16),
                                       freq="1min", inclusive="left"))
    return _bars(idx)


# ── grouping ────────────────────────────────────────────────────────────────

def test_the_daily_and_weekly_labels_are_their_own_table():
    assert BAR_DAYS == {"1d": 1, "1w": 7}
    assert not set(BAR_DAYS) & set(TF_MINUTES), "the intraday table Market Grid replays must not gain them"
    assert set(ALL_TIMEFRAMES) == set(TF_MINUTES) | set(BAR_DAYS)
    assert is_daily_or_longer("1d") and is_daily_or_longer("1w") and not is_daily_or_longer("4h")


def test_futures_daily_bars_are_dated_by_the_trading_day(globex_minutes):
    d = resample_ohlcv(globex_minutes, "1d", day_session_anchor("ES"))
    assert [ts.strftime("%a %m-%d %H:%M") for ts in d.index] == [
        "Mon 08-03 00:00", "Tue 08-04 00:00", "Wed 08-05 00:00", "Thu 08-06 00:00", "Fri 08-07 00:00",
        "Mon 08-10 00:00", "Tue 08-11 00:00", "Wed 08-12 00:00", "Thu 08-13 00:00", "Fri 08-14 00:00",
    ]
    assert set(d["volume"]) == {1380.0}, "every trading day is 23 hours of minutes"
    # Monday's bar opens on the Sunday 18:00 minute and closes on Monday 16:59.
    assert d["open"].iloc[0] == globex_minutes["open"].iloc[0]
    assert d["close"].iloc[0] == globex_minutes.loc[:"2026-08-03 16:59", "close"].iloc[-1]
    monday = globex_minutes.loc["2026-08-02 18:00":"2026-08-03 16:59"]
    assert d["high"].iloc[0] == monday["high"].max() and d["low"].iloc[0] == monday["low"].min()


def test_equity_daily_bars_keep_their_own_date(equity_minutes):
    d = resample_ohlcv(equity_minutes, "1d", day_session_anchor("AAPL"))
    assert [ts.strftime("%a %m-%d %H:%M") for ts in d.index] == [
        "Mon 08-03 00:00", "Tue 08-04 00:00", "Wed 08-05 00:00", "Thu 08-06 00:00", "Fri 08-07 00:00"]
    assert set(d["volume"]) == {390.0}


def test_weekly_bars_start_on_monday_and_hold_the_whole_week(globex_minutes):
    anchor = day_session_anchor("ES")
    d = resample_ohlcv(globex_minutes, "1d", anchor)
    w = resample_ohlcv(globex_minutes, "1w", anchor)
    assert [ts.strftime("%a %m-%d %H:%M") for ts in w.index] == ["Mon 08-03 00:00", "Mon 08-10 00:00"]
    assert list(w["volume"]) == [5 * 1380.0, 5 * 1380.0]
    first_week = d.iloc[:5]
    assert w["open"].iloc[0] == first_week["open"].iloc[0]
    assert w["close"].iloc[0] == first_week["close"].iloc[-1]
    assert w["high"].iloc[0] == first_week["high"].max() and w["low"].iloc[0] == first_week["low"].min()


def test_the_per_bar_vwap_price_stays_intraday(globex_minutes):
    with pytest.raises(ValueError, match="intraday"):
        resample_ohlcv(globex_minutes, "1d", time(18, 0), with_vwap_price=True)


@pytest.mark.parametrize("symbol,expected", [
    ("ES", time(18, 0)), ("NQ", time(18, 0)), ("CL", time(18, 0)), ("GC", time(18, 0)), ("ZN", time(18, 0)),
    ("AAPL", time(0, 0)), ("BTC", time(0, 0)), ("SOMETHING", time(0, 0)), (None, time(0, 0)),
])
def test_a_trading_day_starts_at_the_session_open(symbol, expected):
    assert day_session_anchor(symbol) == expected


def test_daily_spacing_is_recognised_without_the_label(globex_minutes):
    anchor = day_session_anchor("ES")
    assert bars_are_daily_or_longer(resample_ohlcv(globex_minutes, "1d", anchor).index)
    assert bars_are_daily_or_longer(resample_ohlcv(globex_minutes, "1w", anchor).index)
    assert not bars_are_daily_or_longer(resample_ohlcv(globex_minutes, "4h", time(1, 0)).index)
    assert not bars_are_daily_or_longer(globex_minutes.index[:1])


# ── Schwab ──────────────────────────────────────────────────────────────────

def test_schwab_serves_daily_and_weekly_natively():
    assert _fetch_plan("1d") == ("daily", 1, None)
    assert _fetch_plan("1w") == ("weekly", 1, None)
    frame = _bars(pd.date_range("2026-08-03", periods=5, freq="1D"))
    assert build_timeframe(frame, "1d", "ES") is frame, "native bars pass through unaggregated"


class _FakeSchwab:
    def __init__(self):
        self.calls = []

    def price_history(self, **kwargs):
        self.calls.append(kwargs)
        start = kwargs["startDate"].replace(tzinfo=None)
        candles = [{"datetime": int(pd.Timestamp(start + pd.Timedelta(days=i), tz="America/New_York").timestamp() * 1000),
                    "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 10}
                   for i in range(3)]
        return SimpleNamespace(ok=True, status_code=200, text="", json=lambda: {"empty": False, "candles": candles})


def _provider_with(fake) -> SchwabDataProvider:
    provider = object.__new__(SchwabDataProvider)
    provider._client = fake
    provider.session_start = None
    provider._ensure_client = lambda: None
    return provider


def test_schwab_fetches_years_of_daily_bars_in_one_request_with_a_year_period():
    fake = _FakeSchwab()
    df = _provider_with(fake).load("ES", datetime(2006, 9, 16), datetime(2026, 9, 14, 23, 59), "1d")
    assert len(fake.calls) == 1, f"{len(fake.calls)} requests"
    call = fake.calls[0]
    assert (call["frequencyType"], call["frequency"], call["periodType"], call["symbol"]) == ("daily", 1, "year", "/ES")
    assert len(df) == 3


def test_schwab_minute_requests_are_unchanged():
    fake = _FakeSchwab()
    _provider_with(fake).load("ES", datetime(2026, 8, 1), datetime(2026, 9, 14, 23, 59), "5m")
    assert len(fake.calls) == 2, "still chunked into 30-day windows"
    assert all("periodType" not in c for c in fake.calls), "minute requests never carried a period type"


# ── engine, synthetic data, chart payload, report ───────────────────────────

SPEC = get_contract_spec("ES")


@pytest.mark.parametrize("tf", ["1d", "1w"])
def test_synthetic_data_fills_twenty_years(tf):
    start, end = date(2006, 9, 15), date(2026, 9, 14)
    provider = _build_provider("synthetic", "ES", tf, start, end, SPEC)
    df = provider.load("ES", datetime.combine(start, time(0)), datetime.combine(end, time(23, 59)), tf)
    assert (df.index[0] - pd.Timestamp(start)).days <= 7
    assert (pd.Timestamp(end) - df.index[-1]).days <= 7, f"series stops at {df.index[-1]}, short of {end}"
    assert set(df.index.dayofweek) <= ({0, 1, 2, 3, 4} if tf == "1d" else {0})


def test_a_weekly_series_from_a_weekend_start_date_lands_on_mondays():
    saturday = date(2026, 1, 3)
    provider = _build_provider("synthetic", "ES", "1w", saturday, date(2026, 6, 30), SPEC)
    df = provider.load("ES", datetime(2026, 1, 3), datetime(2026, 6, 30, 23, 59), "1w")
    assert len(df) > 20 and set(df.index.dayofweek) == {0}


@pytest.mark.parametrize("tf", ["1d", "1w"])
def test_session_hours_keep_every_daily_and_weekly_bar(tf):
    start, end = date(2024, 1, 1), date(2025, 12, 31)
    provider = _build_provider("synthetic", "ES", tf, start, end, SPEC)
    loaded = provider.load("ES", datetime(2024, 1, 1), datetime(2025, 12, 31, 23, 59), tf)
    engine = BacktestEngine(data_provider=provider, strategy=MACrossoverStrategy(fast=9, slow=21), symbol="ES",
                            timeframe=tf, tick_size=0.25, tick_value=12.5, point_value=50.0,
                            session_start=time(9, 30), session_end=time(16, 0))
    results = engine.run(datetime(2024, 1, 1), datetime(2025, 12, 31, 23, 59))
    assert len(results.price_data) == len(loaded) > 0


def test_session_hours_still_filter_intraday_bars():
    start, end = date(2026, 1, 5), date(2026, 1, 9)
    provider = _build_provider("synthetic", "ES", "5m", start, end, SPEC)
    engine = BacktestEngine(data_provider=provider, strategy=MACrossoverStrategy(fast=9, slow=21), symbol="ES",
                            timeframe="5m", tick_size=0.25, tick_value=12.5, point_value=50.0,
                            session_start=time(9, 30), session_end=time(16, 0))
    results = engine.run(datetime(2026, 1, 5), datetime(2026, 1, 9, 23, 59))
    times = results.price_data.index.time
    assert all(time(9, 30) <= t < time(16, 0) for t in times)


def _daily_results():
    provider = _build_provider("synthetic", "ES", "1d", date(2024, 1, 1), date(2025, 12, 31), SPEC)
    engine = BacktestEngine(data_provider=provider, strategy=MACrossoverStrategy(fast=9, slow=21), symbol="ES",
                            timeframe="1d", tick_size=0.25, tick_value=12.5, point_value=50.0)
    return engine.run(datetime(2024, 1, 1), datetime(2025, 12, 31, 23, 59))


def test_the_chart_is_sent_no_vwap_for_daily_bars():
    ind = price_data_to_response(_daily_results().price_data, time(9, 30))["indicators"]
    for key in ("vwap", "vwap_upper", "vwap_lower"):
        assert all(v is None for v in ind[key]), f"{key} carries values on daily bars"
    assert any(v is not None for v in ind["rsi13"]), "the oscillators are unaffected"


def test_the_report_draws_no_vwap_for_daily_bars():
    names = {t.name for t in _candlestick_chart(_daily_results()).data}
    assert not {"VWAP", "UpperBand", "LowerBand"} & names


def test_weekends_are_skipped_on_a_futures_daily_axis_but_not_a_crypto_one():
    weekdays = pd.bdate_range("2026-08-03", periods=30)
    assert {"bounds": ["sat", "mon"]} in compute_rangebreaks(weekdays)
    every_day = pd.date_range("2026-08-01", periods=30, freq="1D")
    assert {"bounds": ["sat", "mon"]} not in compute_rangebreaks(every_day)
    intraday = pd.date_range("2026-08-03 09:30", periods=200, freq="5min")
    assert {"bounds": ["sat", "mon"]} not in compute_rangebreaks(intraday)


# ── through the API ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("tf", ["1d", "1w"])
def test_a_backtest_runs_on_daily_and_weekly_bars(tf):
    r = client.post("/api/backtests", json={
        "symbol": "ES", "timeframe": tf, "data_source": "synthetic", "strategy_id": "ma_crossover",
        "params": {"fast": 9, "slow": 21}, "start_date": "2016-09-16", "end_date": "2026-09-14",
        "session_start": "09:30", "session_end": "16:00",
    })
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body["timeframe"] == tf and body["data_points"] > (400 if tf == "1d" else 400 // 5)


def test_daily_data_exports_with_session_hours_set():
    r = client.get("/api/data/export", params={
        "symbol": "ES", "timeframe": "1d", "start": "2026-01-05", "end": "2026-03-31",
        "data_source": "synthetic", "format": "csv", "session_start": "09:30", "session_end": "16:00",
    })
    assert r.status_code == 200, r.text[:300]
    rows = [line for line in r.text.splitlines()[1:] if line.strip()]
    assert len(rows) >= 55, f"{len(rows)} daily rows"


@pytest.mark.parametrize("tf", ["1d", "1w"])
def test_market_grid_does_not_offer_daily_or_weekly(tf):
    r = client.post("/api/replay", json={
        "symbol": "ES", "timeframe": tf, "data_source": "synthetic", "strategy_id": "ma_crossover",
        "params": {"fast": 9, "slow": 21}, "start_date": "2026-01-05", "end_date": "2026-01-09",
        "session_start": "09:30", "session_end": "16:00",
    })
    assert r.status_code == 400 and tf in r.text
