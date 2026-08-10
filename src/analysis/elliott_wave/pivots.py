"""
pivots.py
=========

Elliott-specific pivot detection (SRS §4a). Threshold-based directional
change, multi-scale, confirmation-aware.

INDEPENDENCE (SRS FR-1f.2, OQ-21 resolution)
--------------------------------------------
This module does not import, wrap, subclass, or consume the output of
``src/analysis/swing_identification.py``, ``src/analysis/zigzag.py``, or any
other existing pivot/swing detector in this repository. Those modules remain
untouched AND unconsumed. Verified by the import-graph guard test, not a
source-text grep.

WHY DIRECTIONAL CHANGE AND NOT AN N-BAR FRACTAL (FR-1a.5)
----------------------------------------------------------
An N-bar fractal is exactly what ``swing_identification.py`` already
implements. Re-deriving that design -- even without importing it -- would make
this detector independent in name only. Directional change confirms on a PRICE
EVENT (a reversal of theta) rather than a FIXED BAR LAG, which is structurally
different and supplies a non-arbitrary confirmation moment.

NO LOOK-AHEAD (FR-1b)
---------------------
Every pivot carries both ``index`` (bar of the extreme) and ``confirm_index``
(bar at which the reversal completed), and confirm_index > index always. The
final, still-unconfirmed extreme is NEVER emitted -- it has no confirmation
bar, and emitting it would be precisely the look-ahead the split exists to
prevent. Verified by truncation in the test-suite.

This module owns NO Elliott knowledge. It knows nothing about waves, labels,
structures, or degrees. That is what keeps the independence claim auditable.
"""

from __future__ import annotations

import pandas as pd

from .models import EngineConfig, Pivot, PivotKind


def detect_pivots_at_scale(
    df: pd.DataFrame,
    theta: float,
    scale: int,
) -> list[Pivot]:
    """One deterministic pass at a single threshold.

    Maintains a direction and a running extreme; emits a pivot when price
    reverses from that extreme by at least ``theta`` (relative to the extreme's
    own price, FR-1e.1).

    The opening segment has no established direction yet, so both a provisional
    high and a provisional low are tracked; whichever threshold is crossed
    first sets the initial direction and emits the corresponding pivot.
    """
    if theta <= 0:
        raise ValueError("theta must be > 0")

    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    index = df.index
    n = len(highs)
    if n < 2:
        return []

    out: list[Pivot] = []
    direction: str | None = None
    ext_price = highs[0]
    ext_i = 0
    # provisional extremes while direction is still unknown
    seed_hi_p, seed_hi_i = highs[0], 0
    seed_lo_p, seed_lo_i = lows[0], 0

    for i in range(1, n):
        h = highs[i]
        low = lows[i]

        if direction is None:
            if seed_hi_p > 0 and low <= seed_hi_p * (1.0 - theta):
                out.append(Pivot(seed_hi_i, i, index[seed_hi_i], float(seed_hi_p),
                                 PivotKind.HIGH, scale))
                direction, ext_price, ext_i = "down", low, i
            elif seed_lo_p > 0 and h >= seed_lo_p * (1.0 + theta):
                out.append(Pivot(seed_lo_i, i, index[seed_lo_i], float(seed_lo_p),
                                 PivotKind.LOW, scale))
                direction, ext_price, ext_i = "up", h, i
            else:
                if h > seed_hi_p:
                    seed_hi_p, seed_hi_i = h, i
                if low < seed_lo_p:
                    seed_lo_p, seed_lo_i = low, i
            continue

        if direction == "up":
            if h > ext_price:
                ext_price, ext_i = h, i
            elif low <= ext_price * (1.0 - theta):
                out.append(Pivot(ext_i, i, index[ext_i], float(ext_price),
                                 PivotKind.HIGH, scale))
                direction, ext_price, ext_i = "down", low, i
        else:
            if low < ext_price:
                ext_price, ext_i = low, i
            elif h >= ext_price * (1.0 + theta):
                out.append(Pivot(ext_i, i, index[ext_i], float(ext_price),
                                 PivotKind.LOW, scale))
                direction, ext_price, ext_i = "up", h, i

    # FR-1b.3: the trailing extreme is deliberately NOT emitted. It has no
    # confirmation bar yet, so emitting it would be look-ahead.
    return out


def detect_pivots(df: pd.DataFrame, config: EngineConfig | None = None) -> list[Pivot]:
    """Full multi-scale ladder (FR-1d.1).

    Scale 1 is finest. A scale that yields fewer than 2 pivots contributes
    nothing and does not raise (ARCHITECTURE §5.5) -- the caller records the
    exhaustion so a thin analysis is visibly thin.

    Returns pivots ordered by (scale, index) for determinism (FR-1f.1).
    """
    cfg = config or EngineConfig()
    if df is None or len(df) < 2:
        return []
    missing = {"high", "low"} - set(df.columns)
    if missing:
        raise ValueError(f"price_data missing required column(s): {sorted(missing)}")

    all_pivots: list[Pivot] = []
    for k, theta in enumerate(cfg.thresholds(), start=1):
        all_pivots.extend(detect_pivots_at_scale(df, theta, k))
    return all_pivots


def by_scale(pivots: list[Pivot]) -> dict[int, list[Pivot]]:
    """Group pivots by scale, each list ordered by bar index."""
    grouped: dict[int, list[Pivot]] = {}
    for p in pivots:
        grouped.setdefault(p.scale, []).append(p)
    for lst in grouped.values():
        lst.sort(key=lambda p: p.index)
    return grouped


def visible_at(pivots: list[Pivot], bar: int) -> list[Pivot]:
    """Pivots a consumer standing at ``bar`` is allowed to see (FR-1b.2).

    Provided so no caller has to re-derive the no-look-ahead rule, and so the
    truncation test has a single function to exercise.
    """
    return [p for p in pivots if p.confirm_index <= bar]
