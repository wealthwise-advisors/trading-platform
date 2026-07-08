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
