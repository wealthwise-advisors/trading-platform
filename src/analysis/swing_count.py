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
    best_odd: _Pt | None = None      # even phase: highest odd candidate not yet closed beyond
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
                and v(best_odd) > v(last_odd) and closes_beyond(tent.pos, end, v(last_odd)))

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
                    elif v(c) <= v(last_even):
                        flip(c)
                    break
                # The close beyond the last odd may come after the top itself, up
                # to this pullback (see best_odd below).
                valid = last_odd is None or (
                    v(tent) > v(last_odd) and closes_beyond(last_even.pos, c.pos, v(last_odd))
                )
                pulled_back = closes_back(tent.pos, c.pos, s * close[tent.pos])
                if valid and pulled_back:
                    n += 1
                    emit(tent, _label(scale, up, n), seq)
                    last_odd, tent, phase = tent, None, "even"
                    best_odd = None
                    # fall through: c is the first candidate for the pullback
                elif v(c) <= v(last_even):
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
                if v(c) <= v(last_even):
                    flip(c)
                elif tent is None or v(c) < v(tent):
                    tent = c
                    best_odd = None      # odd candidates before the new low no longer count
                break
            if tent is None:
                break
            if v(c) > v(last_odd) and closes_beyond(tent.pos, c.pos, v(last_odd)):
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
    pts = _extend_to_last_candle(pts, high, low, deviation, legs)
    pts = _one_point_per_candle(pts)
    return _restore_wick_hidden_turns(pts, high, low, close, deviation)


def _one_point_per_candle(pts: list[_Pt]) -> list[_Pt]:
    """
    One candle holds one point. A wide candle can be both the highest and the
    lowest of its window, and the turn finder then offered BOTH, in an order the
    rules cannot know -- real /ES 4h 2026-06-09 09:00, high 7491 and low 7247.25
    in one candle: the low was lost and point 3 went to a later wick (7232.25)
    that never closed below it.

    Keep the side that continues the alternation (after a high, the low), then
    join any two same-side neighbours this leaves, keeping the more extreme.
    The wick rule that runs next puts back a turn a wick had hidden.
    """
    out: list[_Pt] = []
    for p in pts:
        if out and out[-1].pos == p.pos:
            prev_kind = out[-2].kind if len(out) > 1 else None
            if prev_kind is not None and out[-1].kind == prev_kind:
                out[-1] = p                  # the one already kept repeats the side before it
            continue
        if out and out[-1].kind == p.kind:   # same side twice: the more extreme stands
            if (p.kind == "H" and p.price > out[-1].price) or (p.kind == "L" and p.price < out[-1].price):
                out[-1] = p
            continue
        out.append(p)
    return out


def _extend_to_last_candle(pts: list[_Pt], high: pd.Series, low: pd.Series, deviation: float, legs: int) -> list[_Pt]:
    """
    The turn finder needs ~legs/2 candles AFTER a turn, so it never sees the
    newest move: the latest point appeared about 6 candles late. Real /ES 5m
    2026-11-10: 15:45 closed above C's point 1, 15:50 made 7559, 15:55 closed
    back below -- sir's rules make that point 3 at 15:55, the app showed nothing.

    From the last turn to the last candle, walk forward with the same
    `deviation` rule: a more extreme price on the same side moves the turn, a
    move back of at least `deviation` starts the next one. The rules then
    judge these points by their closes, like any other.
    """
    if not pts:
        return pts
    H, L = high.to_numpy(float), low.to_numpy(float)
    # Only the candles the turn finder could not judge: its last centre is bar
    # n - (legs // 2 + 1) - 1, so the final legs // 2 + 1 candles are blind.
    # Earlier candles were judged already; walking them again turned every
    # small wiggle into a big point (real /ES 10m 2026-11-09 afternoon: 9 big
    # points, no small ones).
    blind = len(H) - (legs // 2 + 1)
    out = list(pts)
    last = out[-1]
    if last.pos + 1 < blind:   # the newest point is the move's extreme up to the blind candles
        if last.kind == "L":
            j = last.pos + int(np.argmin(L[last.pos:blind]))
            out[-1] = _Pt(j, "L", float(L[j]))
        else:
            j = last.pos + int(np.argmax(H[last.pos:blind]))
            out[-1] = _Pt(j, "H", float(H[j]))
    for k in range(max(out[-1].pos + 1, blind), len(H)):
        cur = out[-1]
        # Moves and new points always land on the move's REAL extreme since
        # the last turn: a lower low just before the blind candles must not be
        # skipped (real /ES 1m 2026-11-11: 15:55 low 7636.75 vs 15:59 7637.50).
        prev = out[-2] if len(out) > 1 else None
        # One candle that goes slightly past the newest point AND past the turn
        # before it: one candle holds one point, and taking out the older turn
        # is the move that matters (real /ES 1m 2026-11-10 11:00: low 7512.00,
        # 0.25 under 10:59, and high 7524.25 over point 2 at 7521.25).
        if cur.kind == "L" and prev is not None and H[k] > prev.price and k > cur.pos:
            out.append(_Pt(k, "H", float(H[k])))
            continue
        if cur.kind == "H" and prev is not None and L[k] < prev.price and k > cur.pos:
            out.append(_Pt(k, "L", float(L[k])))
            continue
        if cur.kind == "L":
            if L[k] < cur.price:
                j = cur.pos + int(np.argmin(L[cur.pos:k + 1]))
                out[-1] = _Pt(j, "L", float(L[j]))
            elif H[k] - cur.price >= deviation * cur.price:
                j = cur.pos + 1 + int(np.argmax(H[cur.pos + 1:k + 1]))
                out.append(_Pt(j, "H", float(H[j])))
        else:
            if H[k] > cur.price:
                j = cur.pos + int(np.argmax(H[cur.pos:k + 1]))
                out[-1] = _Pt(j, "H", float(H[j]))
            elif cur.price - L[k] >= deviation * cur.price:
                j = cur.pos + 1 + int(np.argmin(L[cur.pos + 1:k + 1]))
                out.append(_Pt(j, "L", float(L[j])))
    return out


def _bounce_before_past(P: np.ndarray, Q: np.ndarray, x: int, end: int, s: int) -> float:
    """How far price came back from extreme X (P[x]; s=+1 a high, -1 a low)
    before any candle went past X. Q is the other side (lows for a high)."""
    best = 0.0
    for k in range(x + 1, end):
        if s * P[k] > s * P[x]:
            break
        best = max(best, s * (P[x] - Q[k]))
    return best


def _restore_wick_hidden_turns(pts: list[_Pt], high: pd.Series, low: pd.Series, close: pd.Series,
                               deviation: float) -> list[_Pt]:
    """
    Sir's close rule, applied to the candidates themselves.

    The turn finder joins two lows with no turn between them into one, keeping
    the lower. But when the move made a low X, bounced at least `deviation`,
    and then went below X only BY WICK (no close below X), sir's rules say X
    was the turn and the bounce a point: a new low needs a close beyond.
    Real /ES 5m 2026-11-10: 10:50 low 7503.75 broke point 0, bounced to 7530
    at 11:05, then 11:55 wicked to 7503.00 closing 7505.75 -- the app started
    Swing B at 11:55 and lost 10:50 and 11:05. Same for highs, mirrored.
    """
    H, L, C = high.to_numpy(float), low.to_numpy(float), close.to_numpy(float)
    out = list(pts)
    k = 0
    while k + 1 < len(out):
        a, b = out[k], out[k + 1]
        found = None
        if b.kind == "L":
            run = np.inf
            for x in range(a.pos + 1, b.pos):
                if L[x] >= run:
                    continue
                run = L[x]                                   # x is the move's lowest so far
                if L[b.pos] >= L[x] or (C[x + 1:b.pos + 1] < L[x]).any():
                    continue                                 # b is not lower, or closed below x
                if _bounce_before_past(L, H, x, b.pos, -1) < deviation * L[x]:
                    continue
                y = x + 1 + int(np.argmax(H[x + 1:b.pos]))
                found = (_Pt(x, "L", float(L[x])), _Pt(y, "H", float(H[y])))
                break
        else:
            run = -np.inf
            for x in range(a.pos + 1, b.pos):
                if H[x] <= run:
                    continue
                run = H[x]
                if H[b.pos] <= H[x] or (C[x + 1:b.pos + 1] > H[x]).any():
                    continue
                if _bounce_before_past(H, L, x, b.pos, 1) < deviation * H[x]:
                    continue
                y = x + 1 + int(np.argmin(L[x + 1:b.pos]))
                found = (_Pt(x, "H", float(H[x])), _Pt(y, "L", float(L[y])))
                break
        if found:
            out[k + 1:k + 1] = list(found)                   # re-check (a, x) next round
        else:
            k += 1
    return out


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
