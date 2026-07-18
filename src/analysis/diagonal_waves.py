"""
diagonal_waves.py
==================

Task 6 -- Leading & Ending Diagonal CANDIDATE GENERATION for the top-level
continuous wave count. Mirrors Task 5's ``complex_corrections.py`` exactly
in shape: this module scans the swing series for windows, applies the
diagonal-specific hard rules and shape checks itself (there is no existing
``corrective_waves.py`` diagonal detector to reuse -- diagonals are a
motive-wave pattern, outside that module's corrective-only scope), and
turns a positive read into a plain ``DiagonalCandidate`` that
``wave_numbering._generate_candidates`` adapts into a real ``_Candidate``,
the same shape an impulse or corrective candidate takes.

What makes a diagonal a diagonal (Frost & Prechter)
-------------------------------------------------------
A diagonal is a 5-wave motive-family pattern that breaks ONE of a normal
impulse's hard rules on purpose: **Wave 4 is allowed (in fact required) to
overlap Wave 1's price territory.** Every other impulse-style directional
rule still applies (Wave 2 doesn't retrace past the origin, Wave 3 still
extends beyond Wave 1, Wave 5 still makes some new extreme past Wave 4).
The overall shape is a wedge: waves 1-3-5 and 2-4 trace two converging
(CONTRACTING, the common case) or diverging (EXPANDING, rarer) trend lines.

Two flavors, distinguished by POSITION, not internal shape
----------------------------------------------------------
Per official theory, a **leading diagonal** occurs ONLY as Wave 1 of an
impulse or Wave A of a zigzag (the OPENING move of a new trend); an
**ending diagonal** occurs ONLY as Wave 5 of an impulse or Wave C of a
correction (the CLOSING, exhausting move of an already-extended trend), and
is classically followed by a sharp reversal. Both read identically as an
isolated 6-pivot wedge -- there is no internal geometric test that tells
them apart.

Position classification, revised (Task 6 Improvement, 2026-07-27)
-----------------------------------------------------------------
The original ``_classify_position`` (Task 6) looked BACKWARD only -- a
4-swing net-progress heuristic on the price action immediately before the
diagonal's origin, reasoning that an already-established same-direction
move suggested "ending" (exhaustion). Audited against 709 real diagonal
candidates (ES/NQ/SPY, 5m/15m/1h/4h/1d) by checking what ACTUALLY happened
after each diagonal's Wave 5 -- data the backward-only heuristic never
looked at -- the "ending" calls agreed with genuine subsequent reversal
only 2.5% of the time (1 of 40 clear cases), while "leading" calls agreed
with genuine continuation 97.7% of the time (518 of 530). Further measurement
showed WHY: continuation after any diagonal is simply the overwhelming base
rate in this data (557 of 570 clear-follow-through cases, 97.7%, regardless
of what preceded it) -- the backward heuristic's "leading" accuracy was
tracking that base rate, not genuine positional insight, and its "ending"
signal (a strong preceding same-direction move) carried no measurable
predictive power for what happens next.

``_classify_position`` now looks FORWARD instead: does genuine, decisive
reversal or continuation follow Wave 5 (calibrated thresholds from the
measured real-data distribution -- see ``_ENDING_REVERSAL_THRESHOLD`` /
``_LEADING_CONTINUATION_THRESHOLD``)? This is the only signal this module
has found actual predictive power in. Two consequences, both intentional:
  * When there is no following data yet (the diagonal completed too
    recently -- the realistic LIVE-detection case, or the very end of a
    finite dataset), the result is explicitly ``"unknown"``
    (UNKNOWN_DIAGONAL), never a forced guess (Task 6 Improvement
    requirement 4).
  * This makes the label somewhat retrospective by nature -- it can only be
    determined once enough bars exist AFTER the diagonal. That's an honest
    trade-off, not a defect: this module feeds a DISPLAY/analysis pipeline
    (the Elliott Wave chart overlay and report), never a trading signal
    that must respect real-time causality (confirmed: no ``BaseStrategy``
    consumes ``DiagonalCandidate.position``). See "Known limitations".

Wave 3 vs. Wave 5 length, and truncation
------------------------------------------
Diagonals are widely regarded (including by Prechter himself) as the most
subjective, least rule-rigid Elliott pattern. Two deliberate departures
from ``wave_numbering._grow_count``'s impulse rules, made explicitly here
rather than silently:
  * Wave 3 being the shortest of 1/3/5 is a SOFT quality signal here, not a
    hard rejection (unlike ``_grow_count``'s impulse rule) -- real
    diagonals routinely show progressively shrinking (contracting) or
    growing (expanding) legs where Wave 3 is legitimately not the longest.
  * Wave 5 is only required to make SOME new extreme past Wave 4, NOT to
    exceed Wave 3 (unlike ``_grow_count``'s impulse Wave 5 gate, which
    requires clearing Wave 3). This deliberately accommodates both a
    "throw-under" (barely failing to clear the 1-3 trendline) and outright
    truncation, both commonly documented real diagonal endings.

Internal subdivision -- 5-3-5-3-5 or 3-3-3-3-3?
-------------------------------------------------
Classic Frost & Prechter (1978) describes a leading diagonal's motive legs
(1, 3, 5) as themselves five-wave structures (5-3-5-3-5, like a normal
impulse) while later editions/NEoWave literature allow an all-threes
reading (3-3-3-3-3) for BOTH leading and ending diagonals, and classic
theory requires all-threes specifically for ending diagonals. Given this
genuine disagreement between schools, ``_verify_internal_subdivision``
below no longer picks between two narrow "is it a five" / "is it a three"
checks -- it hands Wave 3's leg to
``structure_classification._unified_recursive_detector`` (Task 3
Improvement, 2026-07-25), which tries EVERY pattern this codebase can
detect (impulse, simple correction, triangle, complex correction, another
diagonal) and reports whichever genuinely resolves. Whatever the leg turns
out to be IS the answer to the 5-vs-3 question for that specific leg,
rather than a forced binary choice between two assumed shapes. This is
still not settling the school-of-thought disagreement in general (a
different leg elsewhere could legitimately resolve differently) -- see
"Known limitations".

Reuse, not reimplementation
------------------------------
Internal subdivision is checked via ``recursive_structure.
verify_recursive_structure`` (generic engine, UNCHANGED signature) using
``structure_classification._unified_recursive_detector`` (Task 3
Improvement) -- ONE detector, not two, reused rather than duplicated, and
itself built entirely out of ALREADY-EXISTING detectors
(``wave_numbering._grow_count``, ``corrective_waves.classify_abc``/
``detect_triangle``/``find_combinations``, this module's own
``_try_diagonal_shape``) -- no new rule-checking logic anywhere in this
module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional

from .swing_identification import Swing, SwingType
from . import structure_classification as sc
from . import recursive_structure as rs

DiagonalPosition = Literal["leading", "ending", "unknown"]

# Below this quality, a candidate is dropped before it ever reaches the
# candidate pool -- mirrors complex_corrections.py's _MIN_QUALITY, same
# role: an ambiguous/marginal wedge fit must never compete for (let alone
# win) a stretch of chart (Task 6, requirement: distinguish diagonals from
# normal impulses -- a weak, coincidental wedge shape is not a real
# distinction).
_MIN_QUALITY = 0.25

# How far past Wave 5 _classify_position looks for genuine follow-through
# (Task 6 Improvement, 2026-07-27 -- see module docstring, "Position
# classification, revised"). CALIBRATED against real data: measured the
# post-Wave-5 reversal-strength distribution across 709 real diagonal
# candidates (ES/NQ/SPY, 5m/15m/1h/4h/1d) -- p90=0.119, p95=0.175, max
# observed=0.476, with genuine strong reversal (>0.3) occurring in only
# 1.8% of cases. Thresholds set from this distribution, not guessed:
_POSITION_LOOKAHEAD = 6
_ENDING_REVERSAL_THRESHOLD = 0.15    # ~p93 -- a genuinely decisive reversal, not noise
_LEADING_CONTINUATION_THRESHOLD = -0.05   # clear continuation, small buffer against zero-crossing noise


@dataclass
class DiagonalCandidate:
    pivots: List[Swing]           # origin + waves 1..5 = 6 pivots
    position: DiagonalPosition    # "leading" | "ending" -- see module docstring
    shape: str                    # "contracting" | "expanding"
    direction: str                # "up" | "down"
    quality: float                 # 0..1, shape-fit confidence (pre-recursion)
    subdivision_bonus: float       # 0..1, from recursive verification (0.0 if unavailable)
    start_pos: int                 # swing-list position of the origin pivot
    end_pos: int                   # swing-list position of wave 5


def _diagonal_quality(legs: List[float], shape: str, wave3_not_shortest: bool) -> float:
    """0..1 -- how cleanly the wedge narrows (contracting) or widens
    (expanding), plus a soft bonus (not a gate -- see module docstring) if
    Wave 3 also happens not to be the shortest motive leg."""
    motive = [legs[0], legs[2], legs[4]]     # waves 1, 3, 5
    corrective = [legs[1], legs[3]]          # waves 2, 4
    if shape == "contracting":
        m_ratio = motive[2] / motive[0] if motive[0] else 1.0
        c_ratio = corrective[1] / corrective[0] if corrective[0] else 1.0
    else:
        m_ratio = motive[0] / motive[2] if motive[2] else 1.0
        c_ratio = corrective[0] / corrective[1] if corrective[1] else 1.0
    convergence = max(0.0, min(1.0, 1.0 - (m_ratio + c_ratio) / 2))
    quality = 0.85 * convergence + (0.15 if wave3_not_shortest else 0.0)
    return round(max(0.15, min(1.0, quality)), 3)


def _classify_position(swings: List[Swing], wave5_pos: int, direction: str) -> DiagonalPosition:
    """See module docstring, "Position classification, revised" -- FOLLOWING
    price action (what genuinely happens after Wave 5) is the only signal
    measured to carry real predictive power for leading-vs-ending; this
    function no longer looks backward at all (see docstring for why the
    original backward-only heuristic was replaced, with evidence).

    Returns "unknown" (Task 6 Improvement requirement 4 -- UNKNOWN_DIAGONAL,
    not a forced guess) whenever there isn't enough following data to judge
    at all (the diagonal completed too recently -- the realistic LIVE-
    detection case, where no "future" bars exist yet) OR the follow-through
    is genuinely ambiguous (neither a clear reversal nor a clear
    continuation, per the calibrated thresholds).
    """
    following = swings[wave5_pos + 1: wave5_pos + 1 + _POSITION_LOOKAHEAD]
    if len(following) < 2:
        return "unknown"   # no following data at all -- e.g. live detection, or end of series

    sign = 1.0 if direction == "up" else -1.0
    move = sign * (following[-1].price - following[0].price)
    churn = sum(abs(following[k].price - following[k - 1].price) for k in range(1, len(following)))
    # positive = price moved AGAINST the diagonal's own direction after wave 5 (a reversal)
    reversal_strength = (-move / churn) if churn > 0 else 0.0

    if reversal_strength > _ENDING_REVERSAL_THRESHOLD:
        return "ending"
    if reversal_strength < _LEADING_CONTINUATION_THRESHOLD:
        return "leading"
    return "unknown"   # genuinely ambiguous follow-through -- neither reads convincingly


def _verify_internal_subdivision(pivots: List[Swing]) -> float:
    """0..1 bonus from recursively verifying Wave 3 -- the diagonal's
    largest, most likely-to-hold-checkable-structure motive leg -- reusing
    recursive_structure.verify_recursive_structure (UNCHANGED engine) and
    structure_classification's UNIFIED recursive detector (Task 3
    Improvement, 2026-07-25 -- see that module's docstring) rather than
    reimplementing detection. Previously tried two separate narrow
    detectors (5-wave-only, 3-wave-only) and took whichever fit better;
    that ad hoc "try both readings" dance is now unnecessary -- the unified
    detector already tries every pattern this codebase can detect
    (impulse, simple correction, triangle, complex correction, diagonal)
    in one pass and reports whichever genuinely resolves, so this is now
    ONE call, not two, with no case-by-case duplication (requirements 3-4).
    Returns 0.0 (no bonus, never a penalty) when no DataFrame context is
    available -- matches the engine's own graceful degradation.
    """
    df = sc.get_recursion_context()
    if df is None:
        return 0.0
    bar_start, bar_end = pivots[2].index, pivots[3].index   # wave 3's own leg (w2 -> w3)
    if bar_end - bar_start < 3:
        return 0.0
    # left=1/right=1, min_swings=3 -- FINER than the engine's own left=2/
    # right=2, min_swings=4 defaults, and deliberately so: measured directly
    # against real data (2026-07-23, 1yr ES 1h), a diagonal's Wave 3 leg is
    # itself already a subdivision of a compact 5-leg pattern (median 5
    # bars, max 13 in the same real dataset) -- at left=2/right=2 even the
    # WIDEST observed leg re-detected only 1 pivot, nowhere near enough for
    # any detector. At left=1/right=1 the widest leg genuinely re-detects a
    # legal read. This still means most (shorter) legs on 1h data won't
    # verify -- an honest, documented limitation, not hidden by loosening
    # past what real data actually supports.
    rv = rs.verify_recursive_structure(
        df, bar_start, bar_end, sc._unified_recursive_detector, "unified",
        max_depth=1, min_swings=3, min_confidence=0.35, left=1, right=1,
    )
    return rv.confidence if rv.verified else 0.0


def _try_diagonal_shape(swings: List[Swing], i: int) -> Optional[DiagonalCandidate]:
    """Pure structural/shape validation ONLY -- hard rules, wedge check,
    quality, position -- with NO recursive subdivision check
    (``subdivision_bonus`` is left at 0.0, a placeholder). ``swings[i]`` is
    the candidate Wave 1; ``swings[i-1]`` is its origin (mirrors
    ``wave_numbering._grow_count``'s own parameter convention). Checks the
    same directional hard rules an impulse enforces (Wave 2 doesn't
    retrace past the origin, Wave 3 extends past Wave 1, Wave 5 makes some
    new extreme past Wave 4) PLUS the one rule that flips: Wave 4 MUST
    overlap Wave 1's territory -- the defining trait of a diagonal, and the
    EXACT OPPOSITE of ``_grow_count``'s own Wave 4 hard rule (never
    modified; reused only by construction -- a window that satisfies the
    impulse's no-overlap rule can never satisfy this one, and vice versa,
    so the two candidate types are mutually exclusive on the same window).

    Split out from ``_try_diagonal`` (Task 3 Improvement, 2026-07-25) so
    ``structure_classification._unified_recursive_detector`` -- itself
    called FROM INSIDE a ``verify_recursive_structure`` recursive step --
    can check "is this local window diagonal-shaped" WITHOUT triggering a
    second, nested, independent recursive_structure call (which
    ``_try_diagonal``'s subdivision check would otherwise start). Nesting a
    fresh top-level recursive call inside a detector callback that is
    ITSELF running inside a recursive call is not infinite (each nested
    call has its own small bounded max_depth), but it IS wasteful, uncached
    duplicate work -- the OUTER recursion already explores this candidate's
    own Wave 3 leg as one of its ``sub_windows`` once ``_try_diagonal_shape``
    reports diagonal-shaped, so a second, independent check inside
    ``_try_diagonal_shape`` itself would just repeat that with different
    cache-key parameters (different left/right/min_swings) and never hit
    the same cache entry. ``_try_diagonal`` (below) adds the real
    subdivision check back for the top-level candidate-generation path,
    which is NOT nested inside any other recursive call.
    """
    if i < 1 or i + 4 >= len(swings):
        return None
    origin = swings[i - 1]
    w1, w2, w3, w4, w5 = swings[i], swings[i + 1], swings[i + 2], swings[i + 3], swings[i + 4]

    kinds = [origin.kind, w1.kind, w2.kind, w3.kind, w4.kind, w5.kind]
    if any(kinds[k] == kinds[k + 1] for k in range(5)):
        return None   # pivots must strictly alternate high/low

    direction = "up" if w1.kind == SwingType.HIGH else "down"
    sign = 1.0 if direction == "up" else -1.0

    len1 = sign * (w1.price - origin.price)
    if len1 <= 0:
        return None

    retrace2 = sign * (w1.price - w2.price) / len1
    if not (0.0 < retrace2 < 1.0):
        return None   # same origin-holding rule impulses enforce

    if sign * (w3.price - w1.price) <= 0:
        return None   # wave 3 must still extend beyond wave 1

    # THE diagonal-defining rule -- see module docstring.
    if not (sign * (w1.price - w4.price) > 0):
        return None   # wave 4 does NOT overlap wave 1 -- this is a normal impulse's job, not this module's

    if sign * (w5.price - w4.price) <= 0:
        return None   # wave 5 must still make SOME new extreme past wave 4 (truncation allowed -- see docstring)

    legs = [abs(w1.price - origin.price), abs(w2.price - w1.price), abs(w3.price - w2.price),
           abs(w4.price - w3.price), abs(w5.price - w4.price)]
    motive = (legs[0], legs[2], legs[4])
    corrective = (legs[1], legs[3])
    contracting = motive[0] > motive[1] > motive[2] and corrective[0] > corrective[1]
    expanding = motive[0] < motive[1] < motive[2] and corrective[0] < corrective[1]
    if not (contracting or expanding):
        return None   # neither a clean wedge-narrowing nor wedge-widening pattern
    shape = "contracting" if contracting else "expanding"

    # Soft signal only (see module docstring) -- legs[2] is wave 3's own leg
    # length; True unless it's strictly shorter than BOTH wave 1 and wave 5.
    wave3_not_shortest = not (legs[2] < legs[0] and legs[2] < legs[4])

    quality = _diagonal_quality(legs, shape, wave3_not_shortest)
    if quality < _MIN_QUALITY:
        return None

    pivots = [origin, w1, w2, w3, w4, w5]
    position = _classify_position(swings, i + 4, direction)   # i+4 = wave 5's own position

    return DiagonalCandidate(
        pivots=pivots, position=position, shape=shape, direction=direction,
        quality=quality, subdivision_bonus=0.0,
        start_pos=i - 1, end_pos=i + 4,
    )


def _try_diagonal(swings: List[Swing], i: int) -> Optional[DiagonalCandidate]:
    """The real, top-level candidate check: shape validation
    (``_try_diagonal_shape``) PLUS the genuine recursive subdivision bonus.
    Safe to call recursion from here -- this function is only ever called
    from ``find_diagonal_candidates``, which runs during
    ``wave_numbering._generate_candidates``'s precompute step, NOT from
    inside any other recursive_structure call.
    """
    cand = _try_diagonal_shape(swings, i)
    if cand is None:
        return None
    cand.subdivision_bonus = _verify_internal_subdivision(cand.pivots)
    return cand


def find_diagonal_candidates(swings: List[Swing]) -> List[DiagonalCandidate]:
    """Slide a 6-pivot window across ``swings``, testing each as a possible
    diagonal Wave 1. O(n) -- one O(1) check per position, same complexity
    class as find_triangle_candidates in complex_corrections.py."""
    out: List[DiagonalCandidate] = []
    for i in range(1, len(swings) - 4):
        cand = _try_diagonal(swings, i)
        if cand is not None:
            out.append(cand)
    return out


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    H, L = SwingType.HIGH, SwingType.LOW

    def _mk(idx: int, price: float, kind: SwingType) -> Swing:
        return Swing(idx, idx + 2, price, kind)

    # Shared wedge: legs 20 -> 16 -> 12 (motive), 10 -> 8 (corrective) --
    # genuinely narrowing, overlaps wave 1 (118 < 120).
    wedge = [_mk(15, 120, H), _mk(18, 110, L), _mk(21, 126, H), _mk(24, 118, L), _mk(27, 130, H)]

    print("=== no following data (e.g. LIVE detection) -> UNKNOWN_DIAGONAL, not a forced guess ===")
    origin = [_mk(12, 100, L)]
    for c in find_diagonal_candidates(origin + wedge):
        print(f"  {c.shape} {c.position} diagonal: quality={c.quality:.2f} span=[{c.start_pos},{c.end_pos}]")

    print("\n=== genuine sharp reversal after wave 5 -> ending ===")
    reversal_after = [_mk(30, 118, L), _mk(33, 122, H), _mk(36, 100, L), _mk(39, 105, H), _mk(42, 85, L)]
    for c in find_diagonal_candidates(origin + wedge + reversal_after):
        print(f"  {c.shape} {c.position} diagonal: quality={c.quality:.2f} span=[{c.start_pos},{c.end_pos}]")

    print("\n=== genuine continuation after wave 5 -> leading ===")
    continuation_after = [_mk(30, 138, H), _mk(33, 132, L), _mk(36, 150, H), _mk(39, 145, L), _mk(42, 165, H)]
    for c in find_diagonal_candidates(origin + wedge + continuation_after):
        print(f"  {c.shape} {c.position} diagonal: quality={c.quality:.2f} span=[{c.start_pos},{c.end_pos}]")

    print("\n=== normal impulse (no overlap) -- expect NO diagonal candidate ===")
    clean = [_mk(0, 100, L), _mk(3, 120, H), _mk(6, 110, L), _mk(9, 140, H),
            _mk(12, 125, L), _mk(15, 160, H)]
    print("  diagonal candidates:", find_diagonal_candidates(clean))
