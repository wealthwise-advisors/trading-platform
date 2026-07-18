"""
swing_identification.py
=======================

Swing (pivot) detection for price-action, Elliott-wave and divergence strategies.

Design goals
------------
1. Deterministic, non-repainting N-bar fractal pivots.
2. Confirmation-aware. A pivot at bar ``i`` is only *known* at bar ``i + right``,
   because you need the right-hand bars to close. The module therefore exposes
   BOTH the pivot index and the confirmation index. In a backtest you must only
   ever act on ``confirm_index`` -- using ``index`` is look-ahead bias and is the
   #1 way swing strategies look great on history and die live.
3. Local-adaptive minimum-move filter (see "Adaptive filtering" below) to drop
   noise pivots and enforce high/low alternation.
4. Market-structure labelling: HH / HL / LH / LL, plus a coarse trend read.

The detection layer (find_swings) is intentionally simple and auditable; the
filtering and labelling layers sit on top so you can swap any piece out.

Adaptive filtering (2026-07-20)
--------------------------------
``filter_swings`` used to accept one absolute ``min_move`` number, computed by
the caller as a single GLOBAL statistic over the whole series (typically
``k * median(ATR)``) and applied identically to every candidate counter-swing
everywhere in the data. Audited and found to actively erase genuine Elliott
pivots: a real, valid Wave 4 (e.g. a ~3% retracement of a much larger Wave 3 --
comfortably inside Elliott's own 14.6-38.2% guideline) can be smaller in
absolute price terms than a threshold sized off the whole series' volatility,
which is dominated by the big Wave 1/3 legs elsewhere in the same chart --
verified directly: constructed exactly this case and watched the Wave 4 pivot
vanish from the filtered list entirely.

The filter now evaluates each candidate counter-swing against its own LOCAL
context instead of one number for the whole chart, combining three signals
computed AT that candidate's own bar position:
  - a fraction of the immediately preceding kept swing's own amplitude
    (``prev_frac``, default 23.6% -- a genuine Wave 2/4 is expected to be
    smaller than the wave it's correcting, so sizing off the PRIOR swing
    keeps a small-but-real retracement eligible even when that prior swing
    was huge)
  - local ATR (Wilder-smoothed volatility AT this bar, not the whole
    series' median -- a quiet period isn't held to a threshold set by a
    separate volatile stretch of the same chart, and vice versa)
  - recent realized volatility -- a short (10-bar) rolling stdev of returns,
    which reacts faster to a genuine regime shift than ATR's longer
    effective memory can

These are combined with **min()**, not max/average: the question for a
candidate pivot is "does this move clear AT LEAST ONE reasonable local
yardstick," not "does it clear the strictest one." The caller's own
``min_move`` (if non-zero) still participates as one more candidate in that
min() -- so it acts as an upper ceiling (preserving the relative strictness
intent behind e.g. Primary's larger multiplier vs Minor's smaller one) rather
than the sole determinant, and callers that explicitly pass ``min_move=0.0``
("keep everything") get that exact behavior unchanged, since 0 is always the
minimum of any combination it's part of.

Trade-off, stated plainly: this is deliberately more PERMISSIVE than the old
global filter -- it will let more small pivots through in exchange for not
silently deleting real ones. Some of what survives now genuinely is noise;
there is no free lunch here. Downstream consumers (wave_numbering.py's hard
rules and candidate scoring) are what's relied on to discard noise that
happens to pass this looser gate, not this filter alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
# Types
# --------------------------------------------------------------------------- #
class SwingType(str, Enum):
    HIGH = "high"
    LOW = "low"


class StructureLabel(str, Enum):
    HH = "HH"  # higher high
    LH = "LH"  # lower high
    HL = "HL"  # higher low
    LL = "LL"  # lower low


@dataclass
class Swing:
    """A single confirmed pivot."""
    index: int                          # bar where the pivot occurred
    confirm_index: int                  # bar where it became known (index + right)
    price: float                        # pivot price (bar high if HIGH, bar low if LOW)
    kind: SwingType
    label: Optional[StructureLabel] = None  # set by label_structure()


# --------------------------------------------------------------------------- #
# 1. Core detection: N-bar fractal
# --------------------------------------------------------------------------- #
def find_swings(high, low, left: int = 2, right: int = 2) -> List[Swing]:
    """Detect swing highs and lows with the N-bar fractal rule.

    A swing high at bar ``i`` requires ``high[i]`` to be strictly greater than the
    ``left`` highs before it and the ``right`` highs after it. Swing low is the
    mirror on ``low``. Strict comparison avoids double-counting flat tops/bottoms.

    Parameters
    ----------
    high, low : array-like of bar highs and lows.
    left, right : number of bars that must be lower (higher) on each side.
        ``right`` is the confirmation lag. Larger values -> fewer, more
        significant pivots, but later confirmation.

    Returns
    -------
    list[Swing] sorted by pivot index (highs and lows interleaved).
    """
    if left < 1 or right < 1:
        raise ValueError("left and right must both be >= 1")

    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    n = len(high)
    swings: List[Swing] = []

    for i in range(left, n - right):
        h = high[i]
        if h > high[i - left:i].max() and h > high[i + 1:i + 1 + right].max():
            swings.append(Swing(i, i + right, float(h), SwingType.HIGH))

        l = low[i]
        if l < low[i - left:i].min() and l < low[i + 1:i + 1 + right].min():
            swings.append(Swing(i, i + right, float(l), SwingType.LOW))

    swings.sort(key=lambda s: s.index)
    return swings


# --------------------------------------------------------------------------- #
# 2. Noise filter: alternation + LOCAL-ADAPTIVE minimum amplitude
# --------------------------------------------------------------------------- #
def _recent_volatility(close, window: int = 10) -> np.ndarray:
    """Short rolling stdev of bar-to-bar price changes (price units, same
    scale as ATR and raw price differences -- not a percentage). Reacts
    faster to a genuine regime shift than Wilder ATR's longer effective
    memory; used as a second, faster-moving adaptive signal alongside ATR
    in ``_adaptive_threshold``. NaN for the first ``window`` bars."""
    close = np.asarray(close, dtype=float)
    diffs = np.diff(close, prepend=close[0])
    out = np.full(len(close), np.nan)
    for i in range(window, len(close)):
        out[i] = float(np.std(diffs[i - window + 1:i + 1], ddof=0))
    return out


def _adaptive_threshold(
    prev_amplitude: Optional[float],
    local_atr: Optional[float],
    recent_vol: Optional[float],
    global_min_move: float,
    prev_frac: float,
    atr_mult: float,
    vol_mult: float,
) -> float:
    """Combine several LOCAL signals into one adaptive minimum-move
    threshold for a single candidate counter-swing, instead of one number
    applied everywhere (see module docstring, "Adaptive filtering").
    min() of whatever's available and positive -- a real but small Wave
    2/4 should survive as long as it clears AT LEAST ONE reasonable local
    yardstick, not all of them at their strictest.
    """
    candidates = [global_min_move]
    if prev_amplitude is not None and prev_amplitude > 0:
        candidates.append(prev_frac * prev_amplitude)
    if local_atr is not None and not np.isnan(local_atr) and local_atr > 0:
        candidates.append(atr_mult * local_atr)
    if recent_vol is not None and not np.isnan(recent_vol) and recent_vol > 0:
        candidates.append(vol_mult * recent_vol)
    return min(candidates)


def filter_swings(
    swings: List[Swing],
    min_move: float = 0.0,
    local_atr_series: Optional[np.ndarray] = None,
    recent_vol_series: Optional[np.ndarray] = None,
    prev_frac: float = 0.236,
    atr_mult: float = 1.0,
    vol_mult: float = 1.0,
) -> List[Swing]:
    """Enforce high/low alternation and drop tiny counter-swings.

    - Consecutive same-type pivots collapse to the more extreme one
      (e.g. two swing highs in a row -> keep the higher).
    - An opposite pivot is ignored if it reverses less than an ADAPTIVE
      threshold from the last kept pivot -- see module docstring,
      "Adaptive filtering", and ``_adaptive_threshold``.

    ``local_atr_series`` / ``recent_vol_series`` (optional): arrays aligned
    to the ORIGINAL bar index space (as produced by ``identify_swings``,
    which is the normal entry point -- direct callers of this function
    without them fall back to the plain global-``min_move`` behavior this
    function always had, since both local signals are simply absent from
    the min() combination). ``min_move`` of 0 with no local series supplied
    keeps everything, exactly as before.
    """
    if not swings:
        return []

    kept: List[Swing] = [swings[0]]
    for s in swings[1:]:
        last = kept[-1]
        if s.kind == last.kind:
            more_extreme = (s.kind == SwingType.HIGH and s.price > last.price) or \
                           (s.kind == SwingType.LOW and s.price < last.price)
            if more_extreme:
                kept[-1] = s
        else:
            prev_amplitude = abs(kept[-2].price - last.price) if len(kept) >= 2 else None
            local_atr = (local_atr_series[s.index]
                        if local_atr_series is not None and s.index < len(local_atr_series) else None)
            recent_vol = (recent_vol_series[s.index]
                         if recent_vol_series is not None and s.index < len(recent_vol_series) else None)
            threshold = _adaptive_threshold(prev_amplitude, local_atr, recent_vol, min_move,
                                            prev_frac, atr_mult, vol_mult)
            if abs(s.price - last.price) >= threshold:
                kept.append(s)
            # else: counter-swing too small relative to its LOCAL context, skip it
    return kept


# --------------------------------------------------------------------------- #
# 3. Structure labelling: HH / HL / LH / LL
# --------------------------------------------------------------------------- #
def label_structure(swings: List[Swing]) -> List[Swing]:
    """Label each pivot relative to the previous pivot of the SAME type.

    Swing highs become HH or LH; swing lows become HL or LL. The first pivot of
    each type has no predecessor, so its label stays None. Mutates and returns
    the list.
    """
    last_high: Optional[float] = None
    last_low: Optional[float] = None

    for s in swings:
        if s.kind == SwingType.HIGH:
            if last_high is not None:
                s.label = StructureLabel.HH if s.price > last_high else StructureLabel.LH
            last_high = s.price
        else:
            if last_low is not None:
                s.label = StructureLabel.HL if s.price > last_low else StructureLabel.LL
            last_low = s.price
    return swings


def trend_state(swings: List[Swing]) -> str:
    """Coarse trend read from the most recent labelled high and low.

    uptrend   = last high is HH and last low is HL
    downtrend = last high is LH and last low is LL
    otherwise = range / transition
    """
    last_high_label = next(
        (s.label for s in reversed(swings)
         if s.kind == SwingType.HIGH and s.label is not None), None)
    last_low_label = next(
        (s.label for s in reversed(swings)
         if s.kind == SwingType.LOW and s.label is not None), None)

    if last_high_label == StructureLabel.HH and last_low_label == StructureLabel.HL:
        return "uptrend"
    if last_high_label == StructureLabel.LH and last_low_label == StructureLabel.LL:
        return "downtrend"
    return "range / transition"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def atr(high, low, close, period: int = 14) -> np.ndarray:
    """Average True Range (Wilder smoothing). Handy for an adaptive min_move."""
    high = np.asarray(high, float)
    low = np.asarray(low, float)
    close = np.asarray(close, float)
    prev_close = np.concatenate(([close[0]], close[:-1]))
    tr = np.maximum.reduce([high - low,
                            np.abs(high - prev_close),
                            np.abs(low - prev_close)])
    out = np.full_like(tr, np.nan)
    if len(tr) >= period:
        out[period - 1] = tr[:period].mean()
        for i in range(period, len(tr)):
            out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def swings_to_frame(swings: List[Swing]) -> pd.DataFrame:
    """Tidy DataFrame view of the detected swings."""
    return pd.DataFrame([{
        "index": s.index,
        "confirm_index": s.confirm_index,
        "kind": s.kind.value,
        "price": round(s.price, 4),
        "label": s.label.value if s.label else None,
    } for s in swings])


# --------------------------------------------------------------------------- #
# One-call pipeline
# --------------------------------------------------------------------------- #
def identify_swings(df: pd.DataFrame, left: int = 2, right: int = 2,
                    min_move: float = 0.0,
                    atr_period: int = 14, vol_window: int = 10,
                    prev_frac: float = 0.236, atr_mult: float = 1.0, vol_mult: float = 1.0,
                    ) -> List[Swing]:
    """detect -> filter -> label. Expects columns 'high' and 'low' (and
    ideally 'close' -- used only to compute the adaptive filter's local ATR
    / recent-volatility signals; falls back to the high/low midpoint if
    'close' is absent, since neither the fractal detection nor the
    structure labelling needs it).

    ``atr_period``/``vol_window``/``prev_frac``/``atr_mult``/``vol_mult``
    tune the adaptive filter (see module docstring, "Adaptive filtering");
    the defaults are reasonable starting points, not tuned per-instrument.
    """
    swings = find_swings(df["high"], df["low"], left, right)
    close = df["close"] if "close" in df.columns else (df["high"] + df["low"]) / 2.0
    local_atr_series = atr(df["high"], df["low"], close, atr_period)
    recent_vol_series = _recent_volatility(close, vol_window)
    swings = filter_swings(swings, min_move, local_atr_series, recent_vol_series,
                           prev_frac, atr_mult, vol_mult)
    swings = label_structure(swings)
    return swings


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    rng = np.random.default_rng(7)
    n = 300
    drift = rng.normal(0, 1, n).cumsum()
    close = 100 + drift + np.sin(np.linspace(0, 12, n)) * 5      # trend + waves
    high = close + rng.uniform(0.2, 1.0, n)
    low = close - rng.uniform(0.2, 1.0, n)
    df = pd.DataFrame({"high": high, "low": low, "close": close})

    a = atr(df["high"], df["low"], df["close"], 14)
    global_min_move = 1.0 * float(np.nanmedian(a))        # require ~1 ATR reversal

    swings = identify_swings(df, left=2, right=2, min_move=global_min_move)
    frame = swings_to_frame(swings)

    print(f"bars={n}  pivots found={len(swings)}  min_move={global_min_move:.2f}")
    print("\nlast 12 confirmed swings:")
    print(frame.tail(12).to_string(index=False))
    print("\ncurrent structure:", trend_state(swings))
    print("confirmation lag = right = 2 bars  ->  act on confirm_index, never index")

    print("\n" + "=" * 70)
    print("OLD (pure global min_move) vs NEW (local-adaptive):")
    print("a genuine, guideline-valid Wave 4 (15% of Wave 3, inside Elliott's")
    print("own 14.6-38.2% range) sitting in the SAME series as an unrelated,")
    print("much more volatile stretch elsewhere in the chart -- exactly the")
    print("real-world case (e.g. one volatile news day inflating a whole")
    print("year's ATR median) that erases a valid pivot under a single global")
    print("threshold, but not under a threshold evaluated locally.")
    print("=" * 70)
    demo_rng = np.random.default_rng(3)
    noisy = 500 + np.cumsum(demo_rng.normal(0, 28, 130))   # unrelated volatile stretch
    w1 = np.linspace(100, 160, 20)
    w2 = np.linspace(160, 130, 8)[1:]
    w3 = np.linspace(130, 330, 40)                          # wave 3: 200pt, smooth
    w4 = np.linspace(330, 300, 8)[1:]                       # wave 4: 30pt retrace = 15% of wave3
    w5 = np.linspace(300, 400, 20)[1:]
    pattern = np.concatenate([w1, w2, w3, w4, w5])
    demo_close = np.concatenate([noisy, pattern])
    demo_df = pd.DataFrame({"high": demo_close + 0.3, "low": demo_close - 0.3, "close": demo_close})
    wave4_bar = len(noisy) + len(w1) + len(w2) + len(w3) + len(w4) - 1

    demo_atr = atr(demo_df["high"], demo_df["low"], demo_df["close"], 14)
    demo_min_move = 2.0 * float(np.nanmedian(demo_atr))   # same 'primary' sensitivity used elsewhere

    old_style = filter_swings(find_swings(demo_df["high"], demo_df["low"], 2, 2), demo_min_move)
    new_style = identify_swings(demo_df, left=2, right=2, min_move=demo_min_move)

    print(f"\nglobal min_move = {demo_min_move:.2f}  (inflated by the unrelated noisy stretch)")
    print(f"Wave 4 retrace = 30.0 (15.0% of Wave 3's 200pt length) at bar {wave4_bar}")
    print("OLD pivots near the pattern:", [(s.index, s.kind.value, round(s.price, 1))
                                           for s in old_style if s.index >= len(noisy)])
    print("NEW pivots near the pattern:", [(s.index, s.kind.value, round(s.price, 1))
                                           for s in new_style if s.index >= len(noisy)])
    print(f"\nWave 4 (bar {wave4_bar}) present:")
    print("  OLD:", any(s.index == wave4_bar for s in old_style))
    print("  NEW:", any(s.index == wave4_bar for s in new_style))
