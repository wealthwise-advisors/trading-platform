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

import pandas as pd


def calc_zigzag(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    deviation: float = 0.001,
    legs: int = 10,
) -> pd.DataFrame:
    """
    Compute zigzag swing points using pandas_ta.
    Returns DataFrame with columns [price, type] where type is 'H' or 'L'.
    """
    import pandas_ta as ta

    result = ta.zigzag(
        high=high, low=low, close=close,
        legs=legs, deviation=deviation,
        retrace=True, last_extreme=False, offset=0,
    )
    if result is None or result.empty:
        return pd.DataFrame(columns=["price", "type"])

    sig_col = f"ZIGZAGs_{deviation*100:.3f}%_{legs}"
    if sig_col not in result.columns:
        sig_col = [c for c in result.columns if c.startswith("ZIGZAGs")][0]

    val_col = sig_col.replace("ZIGZAGs", "ZIGZAGv")

    df = pd.DataFrame(index=result.index)
    df["price"] = result[val_col]
    df["type"] = result[sig_col].map({1: "L", -1: "H"})
    return df[df["price"].notna() & df["type"].notna()]


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
    deviation: float = 0.003,
    legs: int = 3,
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
