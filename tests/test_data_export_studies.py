"""The Export Data file carries what the chart shows, not only OHLC (2026-11-23).

Each study column must equal the chart's own series for the same bars -- the
chart gets them from api/serializers.py, so that is what the export is held to --
the swing columns must equal the chart's swing points (zigzag_to_records), and
columns carry the chart Legend's names.
"""

import io
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from api import serializers
from api.main import app
from src.analysis.indicators import calc_volume_profile

client = TestClient(app)

PARAMS = {"symbol": "ES", "timeframe": "5m", "data_source": "synthetic", "start": "2026-11-16",
          "end": "2026-11-20", "session_start": "09:30", "session_end": "16:00"}
LEVELS = (0.5, 1, 1.5, 2, 2.5, 3, 4, 5)
BANDS = [f"VWAP {s} {'+' if s == 'Upper' else '-'}{lv:.1f}σ" for lv in LEVELS for s in ("Upper", "Lower")]
COLUMNS = (["Open", "High", "Low", "Close", "Volume", "VolumeAvg (20)", "Buyers %", "Buyers", "Sellers",
            "EMA 9", "EMA 20", "EMA 50", "VWAP"] + BANDS
           + ["RSI(2)", "FullK", "FullD", "RSI(13)", "MFI",
              "Volume Delta", "Delta %", "CVD",
              "Price Zone", "VAHigh", "VAH Match", "POC", "POC Match", "VALow", "VAL Match",
              "Swing", "10 Leg", "10 Leg Tag", "3 Leg", "3 Leg Tag",
              "Volume Breakeven", "50% Equilibrium", "Buyer Control", "Buyer Control %"])


def _export(fmt="csv", **extra):
    r = client.get("/api/data/export", params={**PARAMS, "format": fmt, **extra})
    assert r.status_code == 200, r.text[:300]
    return r


def _read(text):
    return pd.read_csv(io.StringIO(text), index_col=0, parse_dates=True,
                       keep_default_na=False, na_values=[""], dtype={"10 Leg": str, "3 Leg": str})


@pytest.fixture(scope="module")
def table():
    return _read(_export().text)


@pytest.fixture(scope="module")
def bars(table):
    return table[["Open", "High", "Low", "Close", "Volume"]].set_axis(["open", "high", "low", "close", "volume"],
                                                                         axis=1)


def test_columns_are_the_charts_studies_in_order(table):
    assert table.index.name == "Time (ET)"
    assert list(table.columns) == COLUMNS


def test_studies_equal_the_charts_series(table, bars):
    ind = serializers.price_data_to_response(bars, pd.Timestamp("09:30").time())["indicators"]
    for col, key in [("RSI(2)", "rsi2"), ("RSI(13)", "rsi13"), ("FullK", "stochrsi_k"), ("FullD", "stochrsi_d"),
                     ("MFI", "mfi"), ("VWAP", "vwap"), ("VWAP Upper +2.0σ", "vwap_upper"),
                     ("VWAP Lower -2.0σ", "vwap_lower"), ("EMA 9", "ema9"),
                     ("Volume Delta", "delta"), ("Delta %", "delta_pct"), ("CVD", "cvd")]:
        chart = np.array([np.nan if v is None else v for v in ind[key]], dtype=float)
        got = table[col].to_numpy(dtype=float)
        assert np.array_equal(np.isnan(chart), np.isnan(got)), col
        assert np.nanmax(np.abs(chart - got)) <= 0.005 + 1e-9, col   # rounded to 2 decimals


def test_bands_are_vwap_plus_level_times_sigma(table):
    sigma = (table["VWAP Upper +2.0σ"] - table["VWAP"]) / 2
    for lv in LEVELS:
        assert (table[f"VWAP Upper +{lv:.1f}σ"] - (table["VWAP"] + lv * sigma)).abs().max() <= 0.05   # each rounded to 2 decimals


def test_swing_columns_equal_the_charts_swing_points(table, bars):
    zz = serializers.zigzag_to_records(bars, dev_3=0.0005, dev_10=0.0010)
    for level, col in (("zigzag_10", "10 Leg"), ("zigzag_3", "3 Leg")):
        want = {pd.Timestamp(p["t"]): (p["label"], p["structure"]) for p in zz[level]}
        got = {ts: (str(v), table.at[ts, f"{col} Tag"]) for ts, v in table[col].dropna().items()}
        assert want and got == want, col


def test_poc_vah_val_are_the_market_grids_per_candle_profile(table, bars):
    # Sir, 2026-11-26: "where is POC match, VAH, VAL". The Market Grid profiles each
    # candle over its timeframe's own days (5m: 2 calendar days) up to and including it.
    for i in (5, len(bars) // 2, len(bars) - 1):
        ts = bars.index[i]
        upto = bars.iloc[:i + 1]
        win = upto[upto.index.normalize() >= ts.normalize() - pd.Timedelta(days=1)]
        vp = calc_volume_profile(win["high"], win["low"], win["close"], win["volume"])
        assert table["POC"].iloc[i] == round(vp["poc"], 2)
        assert table["VAHigh"].iloc[i] == round(vp["vah"], 2) and table["VALow"].iloc[i] == round(vp["val"], 2)
    for v, m in (("POC", "POC Match"), ("VAHigh", "VAH Match"), ("VALow", "VAL Match")):
        ok = table[v].notna()
        assert (table.loc[ok, m] == np.trunc(table.loc[ok, v])).all()   # the whole number, as POC Match groups


def test_price_zone_follows_the_grids_rule(table):
    for _, r in table.dropna(subset=["VAHigh", "VALow", "VWAP"]).iterrows():
        want = ("Buy / Reversal" if r.Close >= r.VAHigh else "Short / Reversal" if r.Close <= r.VALow
                else "Breakout" if r.Close >= r.VWAP else "No trade")
        assert r["Price Zone"] == want


def test_swing_levels_are_sirs_formulas_over_each_swing(table, bars):
    # Volume Breakeven, 50% Equilibrium, Buyer Control: one value per 10 Leg swing,
    # on every candle of that swing (web/src/lib/swingStrength.ts swingBreakeven).
    tagged = table.dropna(subset=["Volume Breakeven"])
    assert len(tagged) and tagged["Swing"].notna().all()
    for name, g in tagged.groupby("Swing"):
        assert g["Volume Breakeven"].nunique() == 1 and g["50% Equilibrium"].nunique() == 1
    zz = serializers.zigzag_to_records(bars, dev_3=0.0005, dev_10=0.0010)["zigzag_10"]
    pts = [p for p in zz if p["swing"] == zz[-1]["swing"]] or zz[-1:]
    if len(pts) > 1:
        s = bars.loc[pd.Timestamp(pts[0]["t"]):pd.Timestamp(pts[-1]["t"])]
        tp = (s["high"] + s["low"] + s["close"]) / 3
        row = table.loc[pd.Timestamp(pts[-1]["t"])]
        assert row["Volume Breakeven"] == pytest.approx((tp * s["volume"]).sum() / s["volume"].sum(), abs=0.006)
        assert row["50% Equilibrium"] == pytest.approx((s["high"].max() + s["low"].min()) / 2, abs=0.006)
        assert 0 <= row["Buyer Control %"] <= 100


def test_central_time_moves_only_the_clock(table):
    ct = _read(_export(tz_offset=-60).text)
    assert ct.index.name == "Time (CT)"
    assert list(ct.index) == [t - timedelta(hours=1) for t in table.index]
    pd.testing.assert_frame_equal(ct.reset_index(drop=True), table.reset_index(drop=True))


def test_unknown_zone_is_refused():
    assert client.get("/api/data/export", params={**PARAMS, "tz_offset": 30}).status_code == 400


def test_excel_sheets_and_levels(bars):
    wb = load_workbook(io.BytesIO(_export("xlsx").content))
    assert wb.sheetnames == ["Price & Studies", "Swing Points", "Levels", "Key"]
    ws = wb["Price & Studies"]
    assert [c.value for c in ws[4]] == ["Time (ET)"] + COLUMNS
    assert ws.freeze_panes == "B5" and ws.max_row == 4 + len(bars)
    assert [c.value for c in wb["Swing Points"][4]] == ["Time (ET)", "Swing", "Level", "Number", "High/Low",
                                                         "Price", "Tag"]
    lv = wb["Levels"]
    assert lv["A5"].value == "Whole range"
    vp = calc_volume_profile(bars["high"], bars["low"], bars["close"], bars["volume"])
    assert lv["D5"].value == round(vp["poc"], 2) and lv["E5"].value == round(vp["vah"], 2)
    assert lv.max_row == 5 + len(set(bars.index.date))          # whole range + one row per day


@pytest.mark.parametrize("fmt", ["pdf", "docx"])
def test_pdf_and_word_still_build(fmt):
    assert len(_export(fmt).content) > 1000
