"""
Swing count by sir's rules (email of 2026-11-12).

Turning points come from sir's candle-close trigger (2026-11-13, see
_trigger_turns): a red candle closing below the last green candle's close
confirms a high, a green candle closing above the last red candle's close
confirms a low. These rules decide which of them count and what they are
called. The same rules run on both scales: 10 Leg (turns of 0.10%+) gives the
big count, 3 Leg (0.05%+) the small count inside each big swing.

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

from src.analysis.zigzag import _alternate_with_majors, _snap_to_extremes, spreadsheet_letter


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
    best_odd: _Pt | None = None      # even phase: highest odd candidate not yet closed beyond
    phase = "odd"

    def v(p: _Pt) -> float:
        return s * p.price

    def closes_beyond(a: int, b: int, level: float) -> bool:
        """Some close in bars (a, b] is beyond `level` in v space.

        Callers start at the even point's OWN bar (pos - 1): its low came first and
        its close after, so a pullback candle that closes above the last high
        already counts (real /ES 10m 2026-11-10 14:40: low 7526.50, close 7539.50
        over point 1's 7535.25 -- point 3 was lost)."""
        seg = s * close[a + 1:b + 1]
        return bool(seg.size) and bool((seg > level).any())

    def closes_back(a: int, b: int, level: float) -> bool:
        seg = s * close[a + 1:b + 1]
        return bool(seg.size) and bool((seg < level).any())

    def breaks(c: _Pt) -> bool:
        """Does c break the protected level (0, or the last even point)?

        Only on a CLOSE, in both directions. Sir's email has the down swing flip
        back up when the bounce "breaks AND CLOSES above" the old high. For the
        up swing it said "takes out the low" (a wick); decided 2026-11-12 to use
        a close there too -- every other rule in the email (1, 3, the flip back)
        needs a close, and the common standard is "bodies break structure, wicks
        sweep". A close AT the low counts: 2 must stay STRICTLY above 0."""
        if v(c) > v(last_even):
            return False
        # The breaking close belongs to THIS pullback: after the swing's latest
        # odd point, not anywhere since the protected level. Real /ES 3m: a
        # close equal to 0 came before the swing's first high, and a gap two
        # days later used it as the break.
        a = last_even.pos
        ref = tent if (phase == "odd" and tent is not None and tent.kind == odd_kind) else last_odd
        if ref is not None and ref.pos > a:
            a = ref.pos
        seg = close[a + 1:c.pos + 1]
        if not seg.size:
            return False
        if up:
            return bool((seg <= last_even.price).any())
        return bool((seg > last_even.price).any())

    def flip(c: _Pt) -> None:
        nonlocal seq, up, s, odd_kind, n, last_odd, last_even, tent, phase, org, best_odd
        best_odd = None
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

    def odd_confirmed_by(end: int) -> bool:
        """Even phase: the best odd candidate so far took out the last odd and
        some close beyond the last odd came after the even point, by bar `end`."""
        return (best_odd is not None and tent is not None and last_odd is not None
                and v(best_odd) > v(last_odd) and closes_beyond(tent.pos - 1, end, v(last_odd)))

    def promote_best_odd() -> None:
        """Confirm the even point; the best odd candidate becomes the forming odd."""
        nonlocal n, last_even, tent, phase, best_odd
        n += 1
        emit(tent, _label(scale, up, n), seq)
        last_even, tent, phase, best_odd = tent, best_odd, "odd", None

    for c in cands:
        again = True
        while again:             # a candidate is looked at again after a phase change
            again = False
            is_odd = c.kind == odd_kind
            if phase == "odd":
                if is_odd:
                    if tent is None or v(c) > v(tent):
                        tent = c
                    break
                # an even-type point after a tentative odd
                if tent is None:
                    if n == 0 and v(c) < v(org) and out and out[-1]["pos"] == org.pos and out[-1]["label"] == "0":
                        # no first point yet: the origin was not the real low
                        shown.discard(org.pos)
                        out.pop()
                        emit(c, "0", seq)
                        org = last_even = c
                    elif breaks(c):
                        flip(c)
                    break
                # The close beyond the last odd may come after the top itself, up
                # to this pullback (see best_odd below).
                valid = last_odd is None or (
                    v(tent) > v(last_odd) and closes_beyond(last_even.pos - 1, c.pos, v(last_odd))
                )
                pulled_back = closes_back(tent.pos, c.pos, s * close[tent.pos])
                if valid and pulled_back:
                    n += 1
                    emit(tent, _label(scale, up, n), seq)
                    last_odd, tent, phase = tent, None, "even"
                    best_odd = None
                    # fall through: c is the first candidate for the pullback
                elif breaks(c):
                    flip(c)
                    break
                else:
                    break

            # phase == "even"
            if not is_odd:
                # A close beyond the last odd may have come AFTER the best odd
                # candidate and before this pullback: real /ES 3m 2026-11-09,
                # 7 = 7598, 8 = 14:54 7575.75, 15:15 wicked to 7600.50, 15:24
                # closed at 7598.75 -- that makes 9, and this low is its pullback.
                if odd_confirmed_by(c.pos - 1):
                    promote_best_odd()
                    again = True
                    continue     # look at c again, now as the pullback of the new odd
                # A real turn back with no close beyond yet: that push failed, and
                # the next push is judged on its own -- "takes out AND closes
                # beyond" is one move (real /ES 3m 2026-11-10: 10:48 wicked under
                # point 3, bounced 26 points, and only the NEXT push closed beyond).
                if best_odd is not None and c.pos > best_odd.pos:
                    best_odd = None
                if breaks(c):
                    flip(c)
                elif tent is None or v(c) < v(tent):
                    tent = c
                break
            if tent is None:
                break
            if v(c) > v(last_odd) and closes_beyond(tent.pos - 1, c.pos, v(last_odd)):
                # The new odd point is the TOP of the move since the even point,
                # even when the candle that closed beyond came later and lower.
                if best_odd is None or v(c) >= v(best_odd):
                    best_odd = c
                promote_best_odd()
            elif best_odd is None or v(c) > v(best_odd):
                best_odd = c
            break

    if phase == "even" and odd_confirmed_by(len(close) - 1):
        promote_best_odd()
    if tent is not None:
        emit(tent, _label(scale, up, n + 1), seq)
    out.sort(key=lambda d: d["pos"])
    return out


def _trigger_turns(open_: np.ndarray, high: np.ndarray, low: np.ndarray, close: np.ndarray,
                   deviation: float) -> list[_Pt]:
    """
    Turning points by sir's candle-close trigger (2026-11-13), the same for highs
    and lows in either direction:

      HIGH  a red candle closes below the close of the last green candle; the
            point is the highest wick of the move, through that red candle.
      LOW   a green candle closes above the close of the last red candle; the
            point is the lowest wick of the move, through that green candle.

    Green = close above open, red = close below open; a doji is neither.
    Highs and lows alternate. A new high before any low has confirmed means the
    move had not turned: the higher one stands (lows the same). A turn smaller
    than `deviation` (0.10% for 10 Leg, 0.05% for 3 Leg) is not counted.
    """
    pts: list[_Pt] = []
    last_green = last_red = None

    def add(kind: str, k: int) -> None:
        # The ABSOLUTE extreme of the move, from just after the last point through
        # the trigger -- covers the green/red pair sir names, and a lower low one
        # candle earlier is not missed (real /ES 5m 2026-11-10: 10:50 at 7503.75
        # vs the pair's 7505.50, the very spot sir flagged on 2026-11-12).
        if not pts:
            start = 0
        elif pts[-1].kind != kind:
            start = pts[-1].pos + 1
        else:                                        # the same move went further
            start = pts[-2].pos + 1 if len(pts) > 1 else 0
        if start > k:
            return
        seg = high[start:k + 1] if kind == "H" else low[start:k + 1]
        j = start + int(np.argmax(seg) if kind == "H" else np.argmin(seg))
        p = _Pt(j, kind, float(seg[j - start]))
        # A wide candle: the last point's OWN candle went on beyond this one (a
        # red candle, its high and then its low) and closed there. One candle holds one point, so the
        # true extreme takes that candle and the last point moves to the best
        # candle before it in its move -- the wide candle's wick past it never
        # closed there. With no candle before it, the last point was no turn.
        # Real /ES 1D 2025-06-13 (6045 down to 5927.50) and 1W 2025-07-28.
        if pts and pts[-1].kind != kind:
            q = pts[-1].pos
            after = (close[q] > open_[q]) if kind == "H" else (close[q] < open_[q])   # came after the point
            # ... and CLOSED beyond it: a wick alone does not count (real /ES 1h
            # 2026-11-11 09:00 wicked to 7593.25 but closed 7608.25, above the low).
            if after and ((close[q] > p.price) if kind == "H" else (close[q] < p.price)):
                lo_ = pts[-2].pos + 1 if len(pts) > 1 else 0
                p = _Pt(q, kind, float(high[q] if kind == "H" else low[q]))
                if q > lo_:
                    other = low[lo_:q] if kind == "H" else high[lo_:q]
                    m = lo_ + int(np.argmin(other) if kind == "H" else np.argmax(other))
                    moved = _Pt(m, pts[-1].kind, float(other[m - lo_]))
                    if abs(p.price - moved.price) < deviation * moved.price:
                        pts.pop()                    # too small a turn once moved: no turn
                        add(kind, k)
                        return
                    pts[-1] = moved
                    pts.append(p)
                else:
                    pts.pop()
                    add(kind, k)
                return
        if not pts:
            pts.append(p)
        elif pts[-1].kind == kind:                   # the same move went further
            if (p.price > pts[-1].price) if kind == "H" else (p.price < pts[-1].price):
                pts[-1] = p
        elif abs(p.price - pts[-1].price) >= deviation * pts[-1].price:
            pts.append(p)

    for k in range(len(close)):
        if close[k] < open_[k]:
            if last_green is not None and close[k] < close[last_green]:
                add("H", k)
            last_red = k
        elif close[k] > open_[k]:
            if last_red is not None and close[k] > close[last_red]:
                add("L", k)
            last_green = k
    return pts


def _candidates(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series,
                deviation: float) -> list[_Pt]:
    pts = _trigger_turns(open_.to_numpy(float), high.to_numpy(float), low.to_numpy(float),
                         close.to_numpy(float), deviation)
    if not pts:
        return []
    # The email starts every count at Point 0, "the absolute swing low where the
    # upward move begins": the lowest low up to the first turn replaces a first
    # low, or comes before a first high.
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
        return pd.DataFrame(columns=["price", "type", "swing", "sub", "label", "structure"])
    df = pd.DataFrame(
        {"price": [p["price"] for p in points], "type": [p["kind"] for p in points],
         "swing": [swing_of(p) for p in points], "label": [p["label"] for p in points]},
        index=index[[p["pos"] for p in points]],
    )
    df["sub"] = df.groupby("swing").cumcount()
    df["structure"] = market_structure(list(df["type"]), list(df["price"]))
    return df[["price", "type", "swing", "sub", "label", "structure"]]


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
    dev_10: float = 0.0010, dev_3: float = 0.0005, open_: pd.Series | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Big (10 Leg) and small (3 Leg) counts as two frames with columns
    [price, type, swing, sub, label], the shape the chart already reads.
    `swing` is the run number of the big count: one run per direction.
    """
    # shortcut: without an open, the previous close stands in for it (candle colour
    # = up/down from the last close); every real chart passes the open.
    if open_ is None:
        open_ = close.shift(1).fillna(close)
    c = close.to_numpy(dtype=float)
    big = count_swings(_candidates(open_, high, low, close, dev_10), c, "big")
    zz10 = _frame(big, high.index, lambda p: p["seq"])

    small: list[dict] = []
    ends = big + [None]
    for a, b in zip(big, ends[1:]):
        lo = a["pos"]
        hi = b["pos"] if b is not None else len(high) - 1
        if hi - lo < 2:
            continue
        sl = slice(lo, hi + 1)
        # Every 3 Leg turn sir's trigger confirms inside the big move. They used
        # to go through the big count's structure rules too, which inside one
        # short leg threw real turns away: whole stretches -- the start of Swing
        # A among them -- had no 3 Leg point (2026-11-13, "3 Leg starts at B 4").
        turns = _trigger_turns(open_.iloc[sl].to_numpy(float), high.iloc[sl].to_numpy(float),
                               low.iloc[sl].to_numpy(float), close.iloc[sl].to_numpy(float), dev_3)
        found = [{"pos": t.pos + lo, "kind": t.kind, "price": t.price} for t in turns if 0 < t.pos < hi - lo]
        parent = b["seq"] if b is not None else a["seq"]
        small += _fit_inside(found, a, b, high, low, parent)
    small.sort(key=lambda d: d["pos"])
    zz3 = _frame(small, high.index, lambda p: p["seq"])
    return zz10, zz3


def market_structure(types: list[str], prices: list[float]) -> list[str]:
    """HH / LH for each high and HL / LL for each low, against the previous point
    of the same kind (the first of each kind is just H / L). What the chart
    writes beside every point (2026-11-13: "mention the highs and lows")."""
    out, last = [], {"H": None, "L": None}
    for k, p in zip(types, prices):
        prev = last[k]
        if prev is None:
            out.append(k)
        elif k == "H":
            out.append("HH" if p > prev else "LH" if p < prev else "EH")
        else:
            out.append("HL" if p > prev else "LL" if p < prev else "EL")
        last[k] = p
    return out


def calc_fine_swings(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series,
                     zz10: pd.DataFrame, zz3: pd.DataFrame) -> pd.DataFrame:
    """
    The finest level, "1 Leg": every turn sir's candle-close trigger confirms,
    with no minimum size, inside each stretch between neighbouring 10 Leg / 3 Leg
    points. Labelled a, b, c ... restarting in every stretch (2026-11-13: "small
    swings in between ... ABCD, alphabetical"). Same columns as zz10 / zz3.
    """
    idx = high.index
    pos = {t: i for i, t in enumerate(idx)}
    anchors = sorted([(pos[t], r["type"], float(r["price"]), int(r["swing"]))
                      for zz in (zz10, zz3) for t, r in zz.iterrows()])
    rows: list[dict] = []
    for (a, ka, pa, sw), b in zip(anchors, anchors[1:] + [None]):
        hi_ = b[0] if b is not None else len(idx) - 1
        if hi_ - a < 2:
            continue
        sl = slice(a, hi_ + 1)
        turns = _trigger_turns(open_.iloc[sl].to_numpy(float), high.iloc[sl].to_numpy(float),
                               low.iloc[sl].to_numpy(float), close.iloc[sl].to_numpy(float), 0.0)
        found = [p for p in turns if 0 < p.pos < hi_ - a]
        if not found:
            continue
        ends = [(a, ka, pa)] + ([(b[0], b[1], b[2])] if b is not None else [])
        majors = pd.DataFrame({"type": [e[1] for e in ends], "price": [e[2] for e in ends]},
                              index=idx[[e[0] for e in ends]])
        minors = pd.DataFrame({"type": [p.kind for p in found], "price": [p.price for p in found]},
                              index=idx[[p.pos + a for p in found]])
        kept = [p for p in _snap_to_extremes(_alternate_with_majors(majors, minors), high, low) if not p[3]]
        parent = b[3] if b is not None else sw
        rows += [{"pos": pos[t], "kind": k, "price": float(pr), "label": spreadsheet_letter(n).lower(), "seq": parent}
                 for n, (t, k, pr, _) in enumerate(kept, start=1)]
    rows.sort(key=lambda d: d["pos"])
    return _frame(rows, idx, lambda p: p["seq"])
