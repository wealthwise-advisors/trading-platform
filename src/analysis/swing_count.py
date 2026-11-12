"""
Swing count by sir's rules (email of 2026-11-12).

Turning points come from the 10 Leg / 3 Leg zigzag (calc_zigzag); these rules
decide which of them count and what they are called. Sir confirmed the same
rules run on both scales: 10 Leg gives the big count, 3 Leg the small count
inside each big swing.

UPTREND (numbers; odd = highs, even = lows)
  0  the swing low where the move starts
  1  the first high; it stands once a later candle closes below its close
  2  the pullback low; must stay above 0
  3  takes out the high of 1 and a candle closes above it
  4, 5, 6 ... alternate the same way: each even a higher low that holds the
     previous even, each odd a new high closed above the previous odd

FLIP (a new swing)
  When a pullback takes out the protected low (0, or the last even low), the
  pending even is cancelled and the count flips into a new swing: the old top
  is its origin, the new low is 1, a bounce that stays below the top is 2, a
  low that takes out 1 and closes below it is 3, and so on (the email's
  "1 or A ... a reverse 1, 2, 3"). Taking out the top flips again. The
  downtrend mirrors the uptrend exactly.

Breaking 0 is by the wick ("takes out the low"); confirming a new odd point is
by a close beyond the previous odd ("takes out ... and closes above it").
Breaking a later even low (4 below 2) flips the same way as breaking 0: the
email's checklist says an even "never breaks the prior even low".

Labels: each swing (one run of a direction) is named A, B, C ...; inside it
the 10 Leg points are 0, 1, 2, 3 ... and the 3 Leg points i, ii, iii ...
A flip starts the next swing letter and the count restarts at 1.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.analysis.zigzag import _alternate_with_majors, _snap_to_extremes, calc_zigzag, spreadsheet_letter


@dataclass
class _Pt:
    pos: int        # bar position
    kind: str       # "H" or "L"
    price: float


def roman(n: int) -> str:
    """1 -> i, 4 -> iv, 9 -> ix, 14 -> xiv (lower case)."""
    out = []
    for value, sym in ((1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
                       (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")):
        while n >= value:
            out.append(sym)
            n -= value
    return "".join(out)


def _label(scale: str, up: bool, n: int) -> str:
    """n >= 1 is the n-th point of a count; n == 0 is an origin."""
    # Sir via the user, 2026-11-12: each new swing (a run in one direction)
    # is named A, B, C...; inside it the 10 Leg points are 1, 2, 3... and the
    # 3 Leg points i, ii, iii..., in either direction. A flip starts a new
    # swing and the count restarts at 1 (the email's "a reverse 1, 2, 3").
    if n == 0:
        return "0"
    return str(n) if scale == "big" else roman(n)


def swing_name(run: int) -> str:
    """Run 1 -> "A", 2 -> "B", 27 -> "AA": the name in a swing's title."""
    return spreadsheet_letter(run)


def count_swings(
    cands: list[_Pt],
    close: np.ndarray,
    scale: str = "big",
    origin: _Pt | None = None,
) -> list[dict]:
    """
    Walk alternating candidate turning points and tag them by the rules above.

    `origin` forces the starting point and direction (used for the small count
    inside one big swing); without it the first candidate is the origin.
    Returns dicts {pos, kind, price, label, seq} in time order, where `seq`
    counts the run of one direction (1 first; +1 at every flip). The last
    point still forming is included with its would-be label.
    """
    if origin is None:
        if not cands:
            return []
        origin, cands = cands[0], cands[1:]

    out: list[dict] = []
    shown: set[int] = set()

    def emit(p: _Pt, label: str, seq: int) -> None:
        out.append({"pos": p.pos, "kind": p.kind, "price": p.price, "label": label, "seq": seq})
        shown.add(p.pos)

    seq = 1
    up = origin.kind == "L"          # a low origin starts an uptrend
    emit(origin, "0", seq)
    org = origin                     # current run's origin (protected until a first even)
    s = 1.0 if up else -1.0          # work in "v" space: odd = max, even = min
    odd_kind = "H" if up else "L"
    n = 0                            # points confirmed in this run
    last_odd: _Pt | None = None
    last_even: _Pt = org             # the protected level
    tent: _Pt | None = None
    phase = "odd"

    def v(p: _Pt) -> float:
        return s * p.price

    def closes_beyond(a: int, b: int, level: float) -> bool:
        """Some close in bars (a, b] is beyond `level` in v space."""
        seg = s * close[a + 1:b + 1]
        return bool(seg.size) and bool((seg > level).any())

    def closes_back(a: int, b: int, level: float) -> bool:
        seg = s * close[a + 1:b + 1]
        return bool(seg.size) and bool((seg < level).any())

    def flip(c: _Pt) -> None:
        nonlocal seq, up, s, odd_kind, n, last_odd, last_even, tent, phase, org
        # New origin: the top of the run that just failed.
        top = last_odd
        if tent is not None and phase == "odd" and (top is None or v(tent) > v(top)):
            top = tent
        if top is None:
            top = org
        seq += 1
        up = not up
        s = -s
        odd_kind = "H" if up else "L"
        n = 0
        last_odd = None
        last_even = top
        org = top
        if top.pos not in shown:
            emit(top, "0", seq)
        tent = c
        phase = "odd"

    for c in cands:
        is_odd = c.kind == odd_kind
        if phase == "odd":
            if is_odd:
                if tent is None or v(c) > v(tent):
                    tent = c
                continue
            # an even-type point after a tentative odd
            if tent is None:
                if n == 0 and v(c) < v(org) and out and out[-1]["pos"] == org.pos and out[-1]["label"] == "0":
                    # no first point yet: the origin was not the real low
                    shown.discard(org.pos)
                    out.pop()
                    emit(c, "0", seq)
                    org = last_even = c
                elif v(c) <= v(last_even):
                    flip(c)
                continue
            valid = last_odd is None or (
                v(tent) > v(last_odd) and closes_beyond(last_even.pos, tent.pos, v(last_odd))
            )
            pulled_back = closes_back(tent.pos, c.pos, s * close[tent.pos])
            if valid and pulled_back:
                n += 1
                emit(tent, _label(scale, up, n), seq)
                last_odd, tent, phase = tent, None, "even"
                # fall through: c is the first candidate for the pullback
            elif v(c) <= v(last_even):
                flip(c)
                continue
            else:
                continue

        # phase == "even"
        if not is_odd:
            if v(c) <= v(last_even):
                flip(c)
            elif tent is None or v(c) < v(tent):
                tent = c
            continue
        if tent is None:
            continue
        if v(c) > v(last_odd) and closes_beyond(tent.pos, c.pos, v(last_odd)):
            n += 1
            emit(tent, _label(scale, up, n), seq)
            last_even, tent, phase = tent, c, "odd"

    if tent is not None:
        emit(tent, _label(scale, up, n + 1), seq)
    out.sort(key=lambda d: d["pos"])
    return out


def _candidates(high: pd.Series, low: pd.Series, close: pd.Series, deviation: float, legs: int) -> list[_Pt]:
    zz = calc_zigzag(high, low, close, deviation=deviation, legs=legs)
    if zz.empty:
        return []
    pos = high.index.get_indexer(zz.index)
    pts = [_Pt(int(p), k, float(pr)) for p, k, pr in zip(pos, zz["type"], zz["price"])]
    # The zigzag needs `legs // 2` candles before a turn, so the opening
    # stretch is never searched: the day's low at the 4th candle of a session
    # was invisible and the count began hours later (real /ES 5m 2026-11-11:
    # low 7593.25 at 09:45, first turn found at 13:05). The email starts every
    # count at Point 0, "the absolute swing low where the upward move begins"
    # (a down count only comes from a flip), so the count begins at the lowest low
    # up to the first turn: it replaces a first low, or comes before a first high.
    # Each turn on the real extreme candle between its neighbouring turns,
    # BEFORE the rules run. The turn finder needs `legs // 2` quiet candles
    # either side, so a wide candle beside a turn is never offered: on real
    # /ES 10m 2026-10-28 a top sat at 12:50 (7787.25) while 14:30 went to
    # 7794.25. Moving points after the rules had judged them broke the rules'
    # own close checks, so the candidates are corrected first.
    idx = high.index
    snapped = _snap_to_extremes([(idx[p.pos], p.kind, p.price, False) for p in pts], high, low)
    pts = [_Pt(int(idx.get_loc(t)), k, float(pr)) for t, k, pr, _ in snapped]
    f = pts[0]
    j = int(np.argmin(low.to_numpy()[: f.pos + 1]))
    start = _Pt(j, "L", float(low.iloc[j]))
    if f.kind == "L":
        if start.price < f.price:
            pts[0] = start
    elif j < f.pos:
        pts.insert(0, start)
    return pts


def _frame(points: list[dict], index: pd.Index, swing_of) -> pd.DataFrame:
    if not points:
        return pd.DataFrame(columns=["price", "type", "swing", "sub", "label"])
    df = pd.DataFrame(
        {"price": [p["price"] for p in points], "type": [p["kind"] for p in points],
         "swing": [swing_of(p) for p in points], "label": [p["label"] for p in points]},
        index=index[[p["pos"] for p in points]],
    )
    df["sub"] = df.groupby("swing").cumcount()
    return df[["price", "type", "swing", "sub", "label"]]


def _fit_inside(found: list[dict], a: dict, b: dict | None, high: pd.Series, low: pd.Series, parent: int) -> list[dict]:
    """
    The small points of one big move, fitted between its two big points and
    numbered i, ii, iii in order.

    Counted on their own, the small points ignored the big points around them:
    the chart drew "3" and "i" side by side as two highs, and some small points
    sat beside the real turn (real /ES 2026-11-12: 49 back-to-back same-side
    points over 4 days of 1m). So, as for the old 3 Leg (zigzag.py), the line
    must go high, low, high through big and small points together, each small
    point on the real extreme candle between its neighbours. Big points never
    move. Numbering then runs i, ii, iii through the move, as in sir's figure.
    """
    if not found:
        return []
    idx = high.index
    ends = [a] + ([b] if b is not None else [])
    majors = pd.DataFrame({"type": [e["kind"] for e in ends], "price": [e["price"] for e in ends]},
                          index=idx[[e["pos"] for e in ends]])
    minors = pd.DataFrame({"type": [p["kind"] for p in found], "price": [p["price"] for p in found]},
                          index=idx[[p["pos"] for p in found]])
    pts = _snap_to_extremes(_alternate_with_majors(majors, minors), high, low)
    kept = [p for p in pts if not p[3]]
    return [{"pos": int(idx.get_loc(t)), "kind": k, "price": float(pr), "label": roman(n), "seq": parent}
            for n, (t, k, pr, _) in enumerate(kept, start=1)]


def calc_swing_count(
    high: pd.Series, low: pd.Series, close: pd.Series,
    dev_10: float = 0.0010, dev_3: float = 0.0005,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Big (10 Leg) and small (3 Leg) counts as two frames with columns
    [price, type, swing, sub, label], the shape the chart already reads.
    `swing` is the run number of the big count: one run per direction.
    """
    c = close.to_numpy(dtype=float)
    big = count_swings(_candidates(high, low, close, dev_10, 3 + 7), c, "big")
    zz10 = _frame(big, high.index, lambda p: p["seq"])

    small: list[dict] = []
    ends = big + [None]
    for a, b in zip(big, ends[1:]):
        lo = a["pos"]
        hi = b["pos"] if b is not None else len(high) - 1
        if hi - lo < 2:
            continue
        sl = slice(lo, hi + 1)
        cands = _candidates(high.iloc[sl], low.iloc[sl], close.iloc[sl], dev_3, 3)
        cands = [_Pt(p.pos + lo, p.kind, p.price) for p in cands]
        cands = [p for p in cands if lo < p.pos < hi]
        start = _Pt(a["pos"], a["kind"], a["price"])
        parent = b["seq"] if b is not None else a["seq"]
        found = [p for p in count_swings(cands, c, "small", origin=start)
                 if p["label"] != "0" and lo < p["pos"] < hi]
        small += _fit_inside(found, a, b, high, low, parent)
    small.sort(key=lambda d: d["pos"])
    zz3 = _frame(small, high.index, lambda p: p["seq"])
    return zz10, zz3
