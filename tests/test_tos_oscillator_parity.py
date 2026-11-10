"""StochRSI and MFI against sir's thinkorswim, to four decimal places.

The values are read off his /ES 1m screenshots of 2026-11-09 (times in ET; his
chart shows Central, an hour earlier). The bars are Schwab's for that session,
saved in tests/fixtures/es_1m_2026_11_09_tos.csv from the 18:00 open before.

His studies: StochRSI(14, 80, 20, WILDERS, CLOSE, 14, 3, 1, SIMPLE) and
MoneyFlowIndex(20, 80, 9, 1) -- oversold 20, overbought 80, length 9, average 1.
"""

from pathlib import Path

import pandas as pd
import pytest

from src.analysis.indicators import calc_mfi, calc_rsi, calc_stochrsi

BARS = pd.read_csv(Path(__file__).parent / "fixtures" / "es_1m_2026_11_09_tos.csv",
                   index_col="timestamp", parse_dates=True)

#           time      FullK     FullD     MFI       RSI(2)    RSI(13)
SIR = [("12:33", 100.0, 95.5363, 69.3907, 98.2077, 76.0521),
       ("12:34", 53.9487, 84.6496, 69.6323, 55.0823, 68.4079),
       ("12:45", 0.0, 5.39589, 34.3517, 16.6312, 41.8076)]


def _at(series, hhmm):
    return series.loc[pd.Timestamp(f"2026-11-09 {hhmm}")]


@pytest.mark.parametrize("hhmm,k,d,mfi,rsi2,rsi13", SIR)
def test_matches_thinkorswim(hhmm, k, d, mfi, rsi2, rsi13):
    full_k, full_d = calc_stochrsi(BARS["close"])
    assert _at(full_k, hhmm) == pytest.approx(k, abs=1e-3)
    assert _at(full_d, hhmm) == pytest.approx(d, abs=1e-3)
    got = calc_mfi(BARS["high"], BARS["low"], BARS["close"], BARS["volume"])
    assert _at(got, hhmm) == pytest.approx(mfi, abs=1e-3)
    assert _at(calc_rsi(BARS["close"], 2), hhmm) == pytest.approx(rsi2, abs=1e-3)
    assert _at(calc_rsi(BARS["close"], 13), hhmm) == pytest.approx(rsi13, abs=1e-3)
