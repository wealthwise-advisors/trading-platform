"""
candlestick_patterns.py
=======================

Rule-based candlestick pattern detection: Doji, Hammer, Bullish/Bearish
Engulfing, Morning Star, Evening Star. Pure OHLC geometry -- no ML, no
training data, deterministic and auditable.

Honesty: candlestick patterns are a weak, noisy signal in isolation.
Confidence scores reflect how closely a bar's geometry matches the textbook
shape, not a probability of the pattern "working" -- validate with the
surrounding trend/structure before acting on any single pattern.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pandas as pd


@dataclass
class CandlestickPattern:
    index: int           # bar index in the DataFrame
    timestamp: object     # bar timestamp
    pattern: str          # e.g. "hammer", "bullish_engulfing"
    direction: str        # "bullish" / "bearish" / "neutral"
    confidence: float     # 0-100


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _bar_geometry(o: float, h: float, l: float, c: float) -> dict:
    body = abs(c - o)
    rng = h - l
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    return {"body": body, "range": rng, "upper_wick": upper_wick, "lower_wick": lower_wick}


def _detect_doji(g: dict) -> float | None:
    """Confidence 0-100, or None if not a doji. Ideal: body/range -> 0."""
    if g["range"] <= 0:
        return None
    ratio = g["body"] / g["range"]
    if ratio > 0.1:
        return None
    return round(100 * _clip01(1 - ratio / 0.1), 1)


def _detect_hammer(g: dict) -> float | None:
    """Confidence 0-100, or None. Ideal: long lower wick (>=2x body), tiny upper wick."""
    if g["body"] <= 0 or g["range"] <= 0:
        return None
    lower_ratio = g["lower_wick"] / g["body"]
    upper_ratio = g["upper_wick"] / g["body"]
    if lower_ratio < 2.0 or upper_ratio > 0.5:
        return None
    lower_score = _clip01((lower_ratio - 2.0) / 2.0)      # saturates at ratio=4
    upper_score = _clip01(1 - upper_ratio / 0.5)
    return round(100 * _clip01(0.5 + 0.35 * lower_score + 0.15 * upper_score), 1)


def _detect_engulfing(prev_o, prev_c, curr_o, curr_c) -> tuple[str, float] | None:
    """Returns (direction, confidence) or None."""
    prev_body = abs(prev_c - prev_o)
    curr_body = abs(curr_c - curr_o)
    if prev_body <= 0 or curr_body <= 0:
        return None

    prev_bearish = prev_c < prev_o
    curr_bullish = curr_c > curr_o
    if prev_bearish and curr_bullish and curr_o <= prev_c and curr_c >= prev_o:
        size_ratio = curr_body / prev_body
        return "bullish", round(100 * _clip01(0.5 + 0.25 * min(size_ratio - 1.0, 2.0) / 2.0), 1)

    prev_bullish = prev_c > prev_o
    curr_bearish = curr_c < curr_o
    if prev_bullish and curr_bearish and curr_o >= prev_c and curr_c <= prev_o:
        size_ratio = curr_body / prev_body
        return "bearish", round(100 * _clip01(0.5 + 0.25 * min(size_ratio - 1.0, 2.0) / 2.0), 1)

    return None


def _detect_star(bar1: dict, bar2_body: float, bar3: dict, bullish: bool) -> float | None:
    """Morning Star (bullish) / Evening Star (bearish). bar1/bar3 are OHLC dicts,
    bar2_body is the middle bar's body size (the 'star')."""
    b1_body = abs(bar1["c"] - bar1["o"])
    b3_body = abs(bar3["c"] - bar3["o"])
    if b1_body <= 0 or b3_body <= 0:
        return None

    if bullish:
        if not (bar1["c"] < bar1["o"]):       # bar1 must be a strong bearish candle
            return None
        if not (bar3["c"] > bar3["o"]):       # bar3 must be bullish
            return None
        midpoint = (bar1["o"] + bar1["c"]) / 2
        if bar3["c"] <= midpoint:
            return None
        retrace = (bar3["c"] - midpoint) / (bar1["o"] - midpoint)
    else:
        if not (bar1["c"] > bar1["o"]):       # bar1 must be a strong bullish candle
            return None
        if not (bar3["c"] < bar3["o"]):       # bar3 must be bearish
            return None
        midpoint = (bar1["o"] + bar1["c"]) / 2
        if bar3["c"] >= midpoint:
            return None
        retrace = (midpoint - bar3["c"]) / (midpoint - bar1["o"])

    small_star = _clip01(1 - (bar2_body / b1_body) / 0.5) if b1_body else 0.0
    retrace_score = _clip01(retrace)
    return round(100 * _clip01(0.4 + 0.35 * retrace_score + 0.25 * small_star), 1)


def detect_candlestick_patterns(df: pd.DataFrame) -> List[CandlestickPattern]:
    """Scan a DataFrame with 'open','high','low','close' for known patterns.
    Returns one entry per detected pattern, sorted by index."""
    out: List[CandlestickPattern] = []
    n = len(df)
    opens, highs, lows, closes = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    idx = df.index

    for i in range(n):
        g = _bar_geometry(opens[i], highs[i], lows[i], closes[i])

        doji_conf = _detect_doji(g)
        if doji_conf is not None:
            out.append(CandlestickPattern(i, idx[i], "doji", "neutral", doji_conf))

        hammer_conf = _detect_hammer(g)
        if hammer_conf is not None:
            out.append(CandlestickPattern(i, idx[i], "hammer", "bullish", hammer_conf))

        if i >= 1:
            res = _detect_engulfing(opens[i - 1], closes[i - 1], opens[i], closes[i])
            if res is not None:
                direction, conf = res
                name = "bullish_engulfing" if direction == "bullish" else "bearish_engulfing"
                out.append(CandlestickPattern(i, idx[i], name, direction, conf))

        if i >= 2:
            bar1 = {"o": opens[i - 2], "c": closes[i - 2]}
            bar3 = {"o": opens[i], "c": closes[i]}
            bar2_body = abs(closes[i - 1] - opens[i - 1])

            morning_conf = _detect_star(bar1, bar2_body, bar3, bullish=True)
            if morning_conf is not None:
                out.append(CandlestickPattern(i, idx[i], "morning_star", "bullish", morning_conf))

            evening_conf = _detect_star(bar1, bar2_body, bar3, bullish=False)
            if evening_conf is not None:
                out.append(CandlestickPattern(i, idx[i], "evening_star", "bearish", evening_conf))

    return out
