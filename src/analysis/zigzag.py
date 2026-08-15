"""
zigzag.py
=========

ZigZag pivot detection and per-swing decimal labeling, extracted verbatim
from ui/components/charts.py so the FastAPI backend and the Streamlit app
share one implementation instead of forking it. No logic changes from the
originals -- this is the fixed-channel swing-numbering algorithm confirmed
working and approved by the user; do not change the labeling rule without
re-confirming against real data (see memory: swing-numbering).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _fractal_extremes(high: pd.Series, low: pd.Series, legs: int):
    """
    Local extremes over a centred window, the first stage of a zigzag.

    Semantics are kept identical to pandas_ta's rolling high/low stage, which
    this replaces: left = floor(legs / 2), right = left + 1, and the window for
    bar i is [i - left, i + right). A bar is a swing low when its low is <= every
    low in that window, a swing high when its high is >= every high in it. A
    flat window can make a bar both, which the alternation step below resolves.

    Returns (positions, kinds, values) in time order, kind +1 high / -1 low.
    """
    h = high.to_numpy(dtype=float)
    l = low.to_numpy(dtype=float)
    m = h.size
    left = legs // 2
    right = left + 1
    win = left + right
    if m < win + 1:
        return np.empty(0, int), np.empty(0, int), np.empty(0, float)

    # Windowed min/max in one vectorised pass -- the scalar version of this is
    # O(n * legs) Python and showed up in profiles on longer ranges.
    hw = np.lib.stride_tricks.sliding_window_view(h, win)
    lw = np.lib.stride_tricks.sliding_window_view(l, win)
    j = np.arange(m - win)                 # window start; centre is j + left
    centres = j + left
    is_low = l[centres] <= lw[j].min(axis=1)
    is_high = h[centres] >= hw[j].max(axis=1)

    pos, kind, val = [], [], []
    for c, lo, hi in zip(centres, is_low, is_high):
        if lo:
            pos.append(c)
            kind.append(-1)
            val.append(l[c])
        if hi:
            pos.append(c)
            kind.append(1)
            val.append(h[c])
    return np.array(pos, int), np.array(kind, int), np.array(val, float)


def _alternate_by_deviation(pos, kind, val, deviation: float):
    """
    Keep alternating high/low extremes separated by at least `deviation`
    (a fraction of price), walking FORWARD in time.

    This replaces pandas_ta.zigzag's own deviation stage (nb_find_zz), which is
    broken. That function scans BACKWARD seeded on the final bar, and its
    "relocate the current extreme" branch is guarded by `zigzags > 1`, so if no
    earlier pivot beats the seed by the threshold it can never advance and the
    whole series collapses to a single pivot. It is a cliff, not a taper, and
    where the cliff falls depends on where the data happens to end. Measured on
    ES 5m 2026-08-10..11, 436 bars, 50.25pt range:

        threshold   pandas_ta   independent reference
          0.08%           32                      87
          0.10%            1                      47
          0.15%            1                      17
          0.20%            1                       5

    A 0.10% (7.8pt) threshold on a 50pt range plainly has more than one
    reversal, so the single-pivot answer is wrong, not merely strict. Walking
    forward and keeping the more extreme of two same-side candidates has no
    such failure mode and degrades smoothly.
    """
    out_pos, out_kind, out_val = [], [], []
    for p, k, v in zip(pos, kind, val):
        if not out_pos:
            out_pos.append(p)
            out_kind.append(k)
            out_val.append(v)
            continue
        if k == out_kind[-1]:
            # Same side: the new extreme supersedes the old one if it is better.
            if (k == 1 and v > out_val[-1]) or (k == -1 and v < out_val[-1]):
                out_pos[-1], out_val[-1] = p, v
            continue
        # Opposite side: only a move of at least `deviation` turns the zigzag.
        ref = out_val[-1]
        if ref > 0 and abs(v - ref) / ref >= deviation:
            out_pos.append(p)
            out_kind.append(k)
            out_val.append(v)
    return out_pos, out_kind, out_val


def calc_zigzag(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    deviation: float = 0.0010,   # 0.10% -- see DEVIATION UNITS below
    legs: int = 10,
) -> pd.DataFrame:
    """
    Compute zigzag swing points.
    Returns DataFrame with columns [price, type] where type is 'H' or 'L'.

    DEVIATION UNITS
    ---------------
    `deviation` is a FRACTION: 0.0010 means a 0.10% reversal. That is the unit
    the API schema and the UI slider use (the slider shows percent and divides
    by 100 before sending), so it is the unit this function accepts.

    WHY THIS IS NOT pandas_ta.zigzag ANY MORE
    -----------------------------------------
    It used to be. pandas_ta's deviation stage collapses the entire series to a
    single pivot above a data-dependent threshold -- see the measurements in
    _alternate_by_deviation. On the shipped 0.10% default that produced exactly
    one swing on a normal ES session, which is what the user saw as "Swing 1"
    appearing alone near the right edge of the chart.

    The fractal stage is reproduced exactly (see _fractal_extremes), so `legs`
    means what it always did; only the broken filter is replaced. `close` is
    accepted for signature compatibility and is not used -- pandas_ta ignored
    it for pivot detection too.

    A swing high is always at its bar's high and a swing low at its bar's low,
    by construction. An earlier version mapped these the wrong way round; see
    tests/test_swing_zigzag_regression.py::TestSwingOrientation.
    """
    if len(high) < 2:
        return pd.DataFrame(columns=["price", "type"])

    pos, kind, val = _fractal_extremes(high, low, legs)
    if pos.size == 0:
        return pd.DataFrame(columns=["price", "type"])

    out_pos, out_kind, out_val = _alternate_by_deviation(pos, kind, val, deviation)
    if not out_pos:
        return pd.DataFrame(columns=["price", "type"])

    return pd.DataFrame(
        {"price": out_val, "type": ["H" if k == 1 else "L" for k in out_kind]},
        index=high.index[out_pos],
    )


def spreadsheet_letter(n: int) -> str:
    """1 -> A, 2 -> B, ... 26 -> Z, 27 -> AA, ... spreadsheet-column style."""
    letters = ""
    x = n
    while x > 0:
        x, rem = divmod(x - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def calc_nested_zigzag(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    zz10: pd.DataFrame,
    deviation: float = 0.0005,   # 0.05% -- the minor zigzag must be
    legs: int = 3,               # finer than the major one it nests inside
) -> pd.DataFrame:
    """
    The minor (3-leg) zigzag, computed INDEPENDENTLY per major (10-leg) swing
    rather than once continuously across the whole series -- each major swing
    in `zz10` (already run through assign_swing_labels(), so it has a `swing`
    column) owns its own, self-contained minor zigzag: `calc_zigzag()` runs
    separately on just that swing's own bar window [swing_start,
    next_swing_start), so no minor pivot from one swing's window can ever
    fall inside the next swing's boundary.

    Tradeoff (explicit, accepted -- structural containment matters more than
    this): pandas_ta.zigzag's fractal detection needs confirming bars on both
    sides of a pivot. Cutting the series at each major swing boundary means
    the last few bars of every swing lose the right-side confirming context
    a single continuous run would have had, so a minor pivot very close to a
    boundary may go undetected that a continuous computation would have
    caught.

    Returns a DataFrame indexed by timestamp with columns [price, type,
    swing, sub, label] -- `swing` is the PARENT major swing number (not an
    independent grouping of the minor zigzag's own price channel), `sub` is
    the minor pivot's 0-indexed position within that parent swing (resets
    for every new parent swing), and `label` is the spreadsheet-style letter
    (A, B, ... Z, AA, ...) for that position.
    """
    empty = pd.DataFrame(columns=["price", "type", "swing", "sub", "label"])
    if zz10.empty:
        return empty

    full_index = high.index
    swing_groups = list(zz10.groupby("swing"))
    frames = []

    for i, (swing_num, grp) in enumerate(swing_groups):
        # x0 is always this swing's OWN first major pivot's timestamp -- the
        # same boundary the visual swing box itself is drawn from (see
        # CandlestickChart.tsx's swingGroups.forEach). The first swing is NOT
        # special-cased to "start of data": bars before the very first major
        # pivot belong to no swing yet, so they get no minor label at all,
        # rather than being folded into swing 1's own count (which used to
        # make its first visible letter start before its own box's left edge).
        x0 = grp.index.min()
        x1 = swing_groups[i + 1][1].index.min() if i + 1 < len(swing_groups) else None
        window = full_index[(full_index >= x0) & (full_index < x1)] if x1 is not None else full_index[full_index >= x0]
        if len(window) < 2:
            continue

        zz_minor = calc_zigzag(high.loc[window], low.loc[window], close.loc[window], deviation=deviation, legs=legs)
        if zz_minor.empty:
            continue

        zz_minor = zz_minor.sort_index().copy()
        # A minor pivot that exactly coincides with one of THIS swing's own
        # major pivots (most commonly its own closing pivot, e.g. "1.1") is
        # already marked by the major overlay's own circle, so it's dropped
        # here -- BEFORE labeling -- rather than only at render time. Doing
        # this after labeling (the previous behavior) let "A" get assigned to
        # a point that was then hidden, silently shifting every visible
        # letter down one (the sequence would visually start at "B").
        # Dropping first means the label sequence is assigned only to pivots
        # that actually get their own circle, so the first visible letter is
        # always "A".
        zz_minor = zz_minor[~zz_minor.index.isin(grp.index)]
        if zz_minor.empty:
            continue

        zz_minor["swing"] = swing_num
        zz_minor["sub"] = range(len(zz_minor))
        zz_minor["label"] = [spreadsheet_letter(n + 1) for n in range(len(zz_minor))]
        frames.append(zz_minor)

    if not frames:
        return empty
    return pd.concat(frames).sort_index()


def assign_swing_labels(zz: pd.DataFrame) -> pd.DataFrame:
    """
    Group ZigZag pivots into swings using a fixed price channel.

    A swing's channel [lower, upper] is set by its FIRST TWO pivots
    (whichever is smaller becomes `lower`, whichever is bigger becomes
    `upper`). Every pivot AFTER that — regardless of whether it is itself a
    High or a Low — is tested against this SAME fixed channel. As long as it
    stays inside [lower, upper] the swing just keeps counting (1.3, 1.4,
    1.5...). The moment a pivot's price goes above `upper` or below `lower`,
    the swing breaks right there and that pivot becomes the first point of
    the next swing — its own price then starts establishing the NEXT swing's
    channel together with the pivot right after it.

    Adds columns: swing (int), sub (int), label (str "swing.sub").
    """
    if zz.empty:
        return zz
    zz = zz.sort_index().copy()
    prices = zz["price"].tolist()

    swing_nums, sub_nums = [], []
    swing_num = 1
    sub_num = 0
    lower = upper = None   # current swing's established channel
    pending = None         # swing's first pivot, waiting for the 2nd to set the channel

    for price in prices:
        if lower is not None and (price > upper or price < lower):
            # Breaks the current swing -> this pivot starts the next swing
            swing_num += 1
            sub_num = 0
            lower = upper = None
            pending = price
        elif lower is None and pending is None:
            # First pivot of a (new) swing
            pending = price
        elif lower is None:
            # Second pivot of the swing -> establishes the channel
            lower, upper = min(pending, price), max(pending, price)
            pending = None
        # else: pivot stayed inside the established channel -> swing just continues

        swing_nums.append(swing_num)
        sub_nums.append(sub_num)
        sub_num += 1

    zz["swing"] = swing_nums
    zz["sub"] = sub_nums
    zz["label"] = [f"{s}.{n}" for s, n in zip(swing_nums, sub_nums)]
    return zz
