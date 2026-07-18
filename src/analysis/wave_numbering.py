"""
wave_numbering.py
==================

Continuous, sequential Elliott Wave numbering across a full swing series.

Philosophy
----------
``elliott_wave.py``'s ``find_impulses()`` answers "is THIS specific 6-pivot
window a legal impulse?" -- a strict, single-window validator. This module
answers a different question: "walking left-to-right through the whole
chart, what continuous wave count would a chart annotate?" -- producing
Wave 1, 2, 3, 4, 5, continuation waves 6..11 (if the move keeps extending),
and a closing a/b/c correction, the way a real Elliott Wave chart service
labels every swing.

This is a from-scratch reimplementation of the numbering approach used by
the wealthwise-advisors/Wealthwise reference repo's ``assign_wave_numbers()``
(``py_scripts/assign_wave_numbers.py``) -- ported to our ``Swing``/
``identify_swings`` pivot model instead of raw pandas-ta zigzag columns,
with corrected defects found in the original:

  1. Wave 4's retracement gate had two different values across branches
     (78.2% in one, 78.6% everywhere else) -- unified to 78.6% here.
  2. The reference re-attempts a fresh count from EVERY pivot -- even
     pivots already claimed by an earlier successful count -- and lets
     later attempts silently overwrite earlier ones on overlap. Verified
     directly against the reference's own code (assign_wave_numbers.py:2391
     `for i in range(1, len(df))`, combined with the unconditional
     `df.at[idx, col] = ...` writes at :2398-2401/:2423-2426, which never
     check whether a value is already present before overwriting). This
     makes Wave 1 "float" to whichever pivot's attempt happened to be
     evaluated last for a given stretch of chart, and the same historical
     candle's label can visibly change between recomputes. Per explicit
     requirement, this module does NOT replicate that: it's a deliberate,
     acknowledged deviation from the reference (which has no concept of
     "prefer the earliest valid start" at all), not an oversight. Once a
     swing is consumed by a kept count, it is never reconsidered by a
     later attempt -- so the earliest valid Wave 1 for a given stretch of
     chart stays Wave 1, and numbering starts as early in the data as a
     valid count can be found.
  3. The ``.1``/``.2`` confidence suffix (both Fibonacci+pattern conditions
     met vs. pattern-only) is computed in the reference but never actually
     used downstream (chart color is identical either way). Here it's a
     real field (``WaveLabel.sub``) meant to drive visual confidence (e.g. a
     dimmer marker for ``.2``).

One non-obvious rule verified line-by-line against the reference's actual
code (not just its comments, which are occasionally stale/misleading) and
carried over faithfully, since it's real and consistent, not a one-off typo:

  * Wave 5's pattern gate requires exceeding **Wave 3**, not Wave 4
    (``df.iloc[i] > df.iloc[i-2]``, which resolves to Wave 3's value) --
    mirrors Wave 3's own gate (must exceed Wave 1): each new impulse leg must
    clear the prior impulse leg, not just the immediately preceding
    retracement.

Deliberate departure from the reference (2026-07-17, per explicit requirement
to enforce textbook Elliott Wave hard rules over reference parity): the
reference's Wave 4 floor/ceiling is Wave 2, not Wave 1
(``df.iloc[start_idx + 1]``), and it never checks whether Wave 3 ends up the
shortest of waves 1/3/5. Both are textbook hard-rule violations (Wave 4 must
not overlap Wave 1's price territory; Wave 3 must never be the shortest of
1, 3, 5) and real violations were confirmed against actual chart output --
this module now enforces both instead of replicating the reference's gaps:

  * Wave 4's gate now floors/ceilings against **Wave 1** (no price overlap
    with wave 1's territory), keeping the existing "genuine pullback off
    Wave 3" check.
  * Wave 5's gate now additionally rejects any candidate that would leave
    Wave 3 as the shortest of waves 1, 3, 5 -- mirroring how a missing Wave 4
    already falls back to a partial 1-2-3 count, a Wave 5 candidate that
    fails this now falls back to a partial 1-2-3-4 count instead of forcing
    an illegal completion.

Momentum divergence (2026-07-17): the website's hard rule "Wave 5 must end
with momentum divergence" is now enforced when an ``rsi`` series is supplied
to ``label_wave_sequence`` / ``_grow_count``. A Wave 5 candidate is only
accepted if price makes a new extreme beyond Wave 3 while RSI does NOT --
i.e. RSI at the candidate is *less* extreme than RSI at Wave 3 (lower RSI on
a new high for an up-impulse; higher RSI on a new low for a down-impulse).
If RSI is unavailable at either point (warm-up NaN) or no ``rsi`` series is
passed at all, the check is skipped rather than blocking the count -- this
mirrors how a missing Wave 4/5 already degrades to a partial count rather
than erroring, and keeps the function usable standalone on bare swings (as
the demo below does) without forcing every caller to supply an indicator.

Selection rewrite (2026-07-18): every rule above governs whether a SINGLE
candidate count is legal. Legality was never the complaint -- a real-data
audit (1 year of ES 1h via Schwab) found the OLD driver attempted 60 separate
Wave-1 starts at "primary" degree, only 6 of which ever reached Wave 5, and
2 of those 6 had a demonstrably higher-Fibonacci-quality alternative
available that was silently skipped -- because the old driver walked
left-to-right and kept whichever candidate passed FIRST, never comparing it
against anything else, and once a swing was consumed it was never
reconsidered even if a later attempt would have told a much cleaner story.
That's the actual complaint: not "is this count legal" but "is this the
BEST count available for this stretch of chart, and is a stray 3-bar
micro-pattern crowding out the chart's actual dominant structure."

The driver is now a proper search, not a greedy walk:
  1. ``_grow_count`` (unchanged -- it already enforces every rule above) is
     run from EVERY swing index as a potential Wave-1, independently, with
     no "already consumed" bookkeeping -- this produces the full universe of
     legal candidates, including many overlapping ones competing for the
     same stretch of chart.
  2. Each candidate is scored (``_score_candidate``) on: average per-leg
     confidence (the existing Fibonacci+pattern ``sub`` signal), a modest
     bonus for reaching further (5 > 4 > 3 -- a complete, self-consistent
     structure is a stronger story, but this is a tiebreaker, not the
     dominant term), and a size bonus so a chart-dominating move outscores a
     same-quality but tiny, inconsequential one. Without that last term the
     highest score always goes to whichever short pattern was easiest to
     satisfy -- exactly the "over-labels internal noise instead of the
     dominant structure" failure this rewrite exists to fix.
  3. ``_select_best_counts`` runs weighted interval scheduling (classic
     resource-scheduling DP, O(n) here since swing indices are a dense
     integer sequence) to choose the subset of NON-OVERLAPPING candidates
     that maximizes total score -- i.e. the single most probable count for
     every stretch of the chart, chosen by comparison, not by who got there
     first. Runners-up that scored within 75% of the winner for the same
     stretch are surfaced as textual alternates rather than silently
     discarded.

Label display (2026-07-18): the ``sub`` confidence marker (1 = Fibonacci
ratio AND price-pattern both confirmed, 2 = pattern only) used to be
appended to the primary label text ("3.2"), which reads exactly like genuine
Elliott sub-wave notation (a wave's own internal 1-2-3-4-5) but means
something completely different -- a confidence score, not a structural
subdivision. ``WaveLabel.label`` now returns the plain wave name ("3");
``sub`` remains available as its own field for callers that want to style
confidence separately (the React chart already dims ``sub == 2`` markers via
opacity -- that's the right place for this signal, not the number itself).

Fibonacci gates (as tuned/validated in the reference, not textbook defaults)
-----------------------------------------------------------------------------
  Wave 2 retraces   38.2% -  85.1% of Wave 1
  Wave 3 extends   161.8% - 261.8% of Wave 1
  Wave 4 retraces    14.6% -  78.6% of Wave 1 (unified; see defect #1 above)
  Wave 5 extends   123.6% - 161.8% of Wave 4

Scope
-----
Impulse waves 1-5 (+ continuation 6-11) and a closing simple a/b/c, PLUS
(2026-07-22, Task 5) triangle and complex-correction (double/triple three)
candidates -- see ``complex_corrections.py`` -- PLUS (2026-07-23, Task 6)
leading & ending diagonal candidates -- see ``diagonal_waves.py``. All three
extra candidate types are generated entirely independently of
``_grow_count``/the impulse structural gate below, reusing existing
detectors wherever one exists, and compete in the SAME candidate pool
scored on a comparable scale so ``_select_best_counts`` (itself unmodified)
can pick whichever reading -- impulse, corrective, or diagonal -- best
explains a given stretch of chart. Diagonal candidates use the SAME "1".."5"
wave labels an impulse does (a diagonal IS a motive-wave pattern, just one
that permits Wave 4 to overlap Wave 1) and are mutually exclusive with
impulse candidates BY CONSTRUCTION on any given window, since a diagonal
requires the overlap an impulse's own hard rule forbids. Simple zigzag/flat
corrections are still NOT generated as top-level candidates here (only as
the closing a/b/c of an impulse, or as complex-correction W/Y/Z sub-parts)
-- see ``complex_corrections.py``'s module docstring for why triangle/
combination/diagonal candidates aren't gated the same way impulse
candidates are.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Literal, Optional

import pandas as pd

from .swing_identification import Swing, SwingType, identify_swings
from .structure_classification import classify_structure_detailed, StructureType
from .complex_corrections import (
    CorrectiveCandidate, find_complex_correction_candidates, find_triangle_candidates,
)
from .diagonal_waves import DiagonalCandidate, find_diagonal_candidates

Direction = Literal["up", "down"]

# --------------------------------------------------------------------------- #
# Fibonacci gates
# --------------------------------------------------------------------------- #
WAVE2_RETRACE = (0.382, 0.851)      # of wave 1
WAVE3_EXTENSION = (1.618, 2.618)    # of wave 1, added past wave 1's end
WAVE4_RETRACE = (0.146, 0.786)      # of wave 1, retraced back from wave 3's end
WAVE5_EXTENSION = (1.236, 1.618)    # of wave 4's length, added past wave 4's end

MAX_CONTINUATION = 11               # cap on continuation waves (mirrors the reference's own cap)


@dataclass
class WaveLabel:
    swing: Swing
    wave: str                       # "1".."11" or "a"/"b"/"c"
    sub: Optional[int]              # 1 (fib+pattern both met) / 2 (pattern only) / None (n/a)
    direction: Direction

    @property
    def index(self) -> int:
        return self.swing.index

    @property
    def price(self) -> float:
        return self.swing.price

    @property
    def label(self) -> str:
        # Plain wave name only -- see module docstring, "Label display
        # (2026-07-18)". `sub` is a confidence score, not Elliott sub-wave
        # notation; callers that want it should read `.sub` separately.
        return self.wave


def _in_range(x: float, lo: float, hi: float) -> bool:
    return lo <= x <= hi


def _rsi_at(rsi: Optional[pd.Series], bar_index: int) -> Optional[float]:
    """Position-based RSI lookup at a swing's bar index. None if unavailable
    (no series supplied, out of range, or still NaN from indicator warm-up)."""
    if rsi is None or not (0 <= bar_index < len(rsi)):
        return None
    v = rsi.iloc[bar_index]
    return None if pd.isna(v) else float(v)


def _first_hit(swings: List[Swing], first_idx: int,
               predicate: Callable[[Swing], bool]) -> Optional[int]:
    """Try swings[first_idx]; on failure, retry at swings[first_idx + 2]
    (skip one opposite-kind pivot, landing on the next same-kind extreme --
    mirrors the reference's ``i += 2`` "try the next same-direction pivot"
    fallback). Returns the accepted index, or None if both fail / run out.
    """
    for j in (first_idx, first_idx + 2):
        if j >= len(swings):
            return None
        if predicate(swings[j]):
            return j
    return None


# --------------------------------------------------------------------------- #
# Grow one candidate count forward from a Wave-1 seed
# --------------------------------------------------------------------------- #
def _grow_count(swings: List[Swing], start: int,
                rsi: Optional[pd.Series] = None
                ) -> Optional[tuple[List[WaveLabel], int, List[str]]]:
    """Try to build a wave count with Wave 1 = swings[start] (swings[start-1]
    is its origin). Returns (labels, next_unconsumed_index, warnings) if it
    reaches at least Wave 3, else None.

    ``rsi`` (optional): position-indexed RSI series used to gate Wave 5 on
    momentum divergence (see module docstring). Omit for the pure price-only
    behavior. When supplied, a Wave 5 candidate whose RSI can't be evaluated
    at Wave 3 or itself is rejected outright (never silently passed) and a
    message explaining why is returned in ``warnings``.
    """
    if start < 1 or start >= len(swings):
        return None

    origin = swings[start - 1]
    w1 = swings[start]
    direction: Direction = "up" if w1.kind == SwingType.HIGH else "down"
    sign = 1.0 if direction == "up" else -1.0

    len1 = sign * (w1.price - origin.price)
    if len1 <= 0:
        return None

    labels: List[WaveLabel] = [WaveLabel(w1, "1", None, direction)]

    # ---- Wave 2: gated retracement of Wave 1. No retry -- an immediate
    # failure invalidates this whole candidate (mirrors the reference, the
    # one transition with no skip-ahead fallback). ----
    if start + 1 >= len(swings):
        return None
    w2 = swings[start + 1]
    retrace2 = sign * (w1.price - w2.price) / len1
    # Hard rule: wave 2 must not retrace to (let alone beyond) wave 1's
    # origin -- strict upper bound. Found via real-data validation
    # (2026-07-17): the previous inclusive `<= 1.0` accepted a Wave 2 that
    # closes exactly back to the origin price (100.000000% retracement,
    # confirmed tick-for-tick on live ES/NQ/MES data), which erases Wave 1's
    # net progress entirely -- a degenerate count, not a legal one.
    if not (0.0 < retrace2 < 1.0):    # stays strictly within (origin, wave1) -- w2_holds_origin
        return None
    sub2 = 1 if _in_range(retrace2, *WAVE2_RETRACE) else 2
    labels.append(WaveLabel(w2, "2", sub2, direction))
    cursor = start + 1

    # ---- Wave 3: gated extension of Wave 1, one skip-ahead retry ----
    def _w3_ok(c: Swing) -> bool:
        return c.kind == w1.kind and sign * (c.price - w1.price) > 0  # w3_exceeds_w1

    idx3 = _first_hit(swings, cursor + 1, _w3_ok)
    if idx3 is None:
        return None  # wave 3 never established -- discard the whole attempt
    w3 = swings[idx3]
    ext3 = sign * (w3.price - w1.price) / len1
    sub3 = 1 if _in_range(ext3, *WAVE3_EXTENSION) else 2
    labels.append(WaveLabel(w3, "3", sub3, direction))
    cursor = idx3
    len3 = sign * (w3.price - w2.price)   # wave 3's own leg length (w2 -> w3)

    # ---- Wave 4: gated retracement of Wave 1 (measured off Wave 3), one
    # skip-ahead retry. Failure here still keeps the 1-2-3 partial count. ----
    def _w4_ok(c: Swing) -> bool:
        # Hard rule: wave 4 must not overlap wave 1's price territory --
        # floor/ceiling is Wave 1, not Wave 2 (see module docstring,
        # "deliberate departure from the reference").
        return (c.kind == origin.kind
                and sign * (c.price - w1.price) > 0    # no overlap with wave 1 (hard rule)
                and sign * (w3.price - c.price) > 0)   # genuine pullback off wave 3

    idx4 = _first_hit(swings, cursor + 1, _w4_ok)
    if idx4 is None:
        return labels, cursor + 1, []
    w4 = swings[idx4]
    retrace4 = sign * (w3.price - w4.price) / len1
    sub4 = 1 if _in_range(retrace4, *WAVE4_RETRACE) else 2
    labels.append(WaveLabel(w4, "4", sub4, direction))
    cursor = idx4

    # ---- Wave 5: gated extension of Wave 4, one skip-ahead retry. Failure
    # here still keeps the 1-2-3-4 partial count. ----
    len4 = sign * (w3.price - w4.price)
    warnings: List[str] = []
    rsi_w3 = _rsi_at(rsi, w3.index)

    def _w5_structural_ok(c: Swing) -> bool:
        # Gate is "exceeds Wave 3", not "exceeds Wave 4" -- confirmed against
        # the reference's actual code (its Wave 5 gate is
        # `df.iloc[i] > df.iloc[i-2]`, which resolves to Wave 3's value, not
        # Wave 4's). Mirrors Wave 3's own gate (must exceed Wave 1): each new
        # impulse leg must exceed the prior impulse leg, not just the
        # immediately preceding retracement.
        len5 = sign * (c.price - w4.price)
        return (c.kind == w1.kind
                and sign * (c.price - w3.price) > 0
                # Hard rule: wave 3 must never be the shortest of 1, 3, 5.
                and not (len3 < len1 and len3 < len5))

    def _w5_ok(c: Swing) -> bool:
        if not _w5_structural_ok(c):
            return False
        if rsi is None:
            return True   # caller opted out of the momentum-divergence check entirely
        # Hard rule: Wave 5 must end with momentum divergence -- price makes
        # a new extreme beyond Wave 3 while RSI does not. Per explicit
        # requirement, a candidate is REJECTED (not passed through) when RSI
        # can't be evaluated at either point -- Wave 5 must never complete on
        # unconfirmable momentum. The caller is warned separately (below).
        rsi_c = _rsi_at(rsi, c.index)
        if rsi_w3 is None or rsi_c is None:
            return False
        return sign * (rsi_w3 - rsi_c) > 0   # RSI less extreme than at wave 3

    idx5 = _first_hit(swings, cursor + 1, _w5_ok)
    if idx5 is None:
        if rsi is not None:
            candidates = [swings[j] for j in (cursor + 1, cursor + 3) if j < len(swings)]
            structurally_valid = [c for c in candidates if _w5_structural_ok(c)]
            missing_rsi = any(rsi_w3 is None or _rsi_at(rsi, c.index) is None
                              for c in structurally_valid)
            if structurally_valid and missing_rsi:
                warnings.append(
                    f"Wave 5 unconfirmed for the {direction}-count starting at bar "
                    f"{w1.index}: momentum divergence could not be evaluated "
                    f"(RSI unavailable at bar {w3.index if rsi_w3 is None else structurally_valid[0].index})."
                )
        return labels, cursor + 1, warnings
    w5 = swings[idx5]
    ext5 = sign * (w5.price - w4.price) / len4
    sub5 = 1 if _in_range(ext5, *WAVE5_EXTENSION) else 2
    labels.append(WaveLabel(w5, "5", sub5, direction))
    cursor = idx5

    # ---- Continuation (6..11), or a closing a/b/c ----
    cursor = _extend_or_close(swings, cursor, sign, direction, labels)

    return labels, cursor + 1, warnings


def _extend_or_close(swings: List[Swing], cursor: int, sign: float, direction: Direction,
                     labels: List[WaveLabel]) -> int:
    """After Wave 5 (swings[cursor]), keep numbering 6..MAX_CONTINUATION while
    price keeps making new extremes in the trend direction; once that stops,
    label one more alternating triple as a closing a/b/c if it shows a clean
    reversal. Returns the new cursor (index of the last consumed swing).
    """
    n = len(swings)
    trend_kind = swings[cursor].kind
    last_trend_price = swings[cursor].price
    wave_num = 6

    while wave_num <= MAX_CONTINUATION and cursor + 2 < n:
        pullback, extreme = swings[cursor + 1], swings[cursor + 2]
        if extreme.kind != trend_kind or sign * (extreme.price - last_trend_price) <= 0:
            break
        labels.append(WaveLabel(pullback, str(wave_num), None, direction))
        wave_num += 1
        labels.append(WaveLabel(extreme, str(wave_num), None, direction))
        wave_num += 1
        last_trend_price = extreme.price
        cursor += 2

    if cursor + 3 < n:
        a, b, c = swings[cursor + 1], swings[cursor + 2], swings[cursor + 3]
        reversal = (a.kind != trend_kind and sign * (last_trend_price - a.price) > 0
                    and b.kind == trend_kind and c.kind != trend_kind
                    and sign * (c.price - a.price) < 0)
        if reversal:
            labels.append(WaveLabel(a, "a", None, direction))
            labels.append(WaveLabel(b, "b", None, direction))
            labels.append(WaveLabel(c, "c", None, direction))
            cursor += 3

    return cursor


# --------------------------------------------------------------------------- #
# Candidate scoring
# --------------------------------------------------------------------------- #
# Per-leg confidence: Fibonacci ratio + price-pattern both held (1), only the
# pattern held (2), or not fib-scored at all -- Wave 1 has no prior wave to
# ratio against, so it's excluded from the average entirely rather than
# guessed at (see _score_candidate).
_SUB_SCORE = {1: 1.0, 2: 0.5}

# Reaching further is a MUCH stronger, more self-consistent story -- steep on
# purpose (2026-07-18 fix, see below), not a mild tiebreaker.
_COMPLETION_BONUS = {2: 0.0, 3: 0.3, 4: 0.6, 5: 1.2}

# How much a structure's SIZE (bars spanned, relative to the whole chart)
# counts toward its score. Without this, the highest score always goes to
# whichever short pattern was easiest to satisfy -- the "over-labels
# internal noise instead of the dominant structure" failure mode this
# rewrite exists to fix. Fibonacci ratios are scale-invariant, so a 5-bar
# noise blip and a 500-bar trend can score identically on fit alone; size
# is what breaks that tie in favor of the one that's actually significant.
_SIZE_WEIGHT = 0.5

# Fixed cost applied per SELECTED candidate in the DP objective (not baked
# into the stored .score, which stays a pure quality reading used for the
# alternates comparison). Found necessary by direct measurement on the
# canonical demo data: a single complete 1-2-3-4-5-a-b-c candidate scored
# 1.488, but splitting the SAME stretch into two incomplete 1-2-3 fragments
# scored 0.925 each -- 1.850 combined, so naive sum-maximizing selection
# preferred the fragmented, less useful reading purely because two
# mediocre pieces summed higher than one good one. A per-candidate penalty
# fixes this: fragmenting the same ground into more pieces pays this cost
# every time, so it only wins when each extra piece is genuinely strong
# enough to be worth its own count -- not just enough to be legal.
_FRAGMENTATION_PENALTY = 0.9


def _score_candidate(labels: List[WaveLabel], total_span: int) -> float:
    """Composite confidence score for one candidate wave count -- this is
    what lets the driver pick the single most probable count for a stretch
    of chart instead of whichever one a left-to-right walk finds first."""
    core = [w for w in labels if w.wave in ("2", "3", "4", "5")]
    leg_conf = sum(_SUB_SCORE.get(w.sub, 0.75) for w in core) / len(core) if core else 0.0
    highest = max((int(w.wave) for w in labels
                   if w.wave.isdigit() and int(w.wave) <= 5), default=2)
    completion = _COMPLETION_BONUS.get(highest, 1.2)
    span = labels[-1].index - labels[0].index
    size = min(span / total_span, 1.0) if total_span > 0 else 0.0
    return leg_conf + completion + _SIZE_WEIGHT * size


# Task 5: comparable "reaching further is a stronger story" bonus for
# corrective candidates, mirroring _COMPLETION_BONUS's role for impulses
# above (that dict itself is untouched -- this is a separate constant for a
# separate candidate type).
#
# CALIBRATED against real data (2026-07-22, 1yr ES 1h, same discipline as
# the NET_PROGRESS_TRENDING fix in Task 2): an initial guess of {triangle:
# 1.0, double_three: 0.7, triple_three: 1.0} was measured directly against
# real-data selection results and produced complex corrections winning 48 of
# 73 selected counts (66%) -- implausible for real Elliott Wave frequency,
# where combinations are the rarest, most caveat-laden pattern. Two causes,
# both fixed here rather than by touching protected code:
#   1. combinations structurally span MORE bars than impulses purely because
#      they need more pivots to qualify at all (a triple three needs 12, an
#      impulse needs as few as 6 to reach Wave 3) -- median measured span was
#      33 bars for corrective candidates vs. 14 for impulse, so the shared
#      size term was rewarding pattern verbosity, not genuine chart
#      dominance. _CORRECTIVE_SIZE_WEIGHT (below) discounts this rather than
#      touching _SIZE_WEIGHT itself, which impulse scoring also depends on.
#   2. triple_three previously earned MORE completion credit than
#      double_three ("more confirmed joints = more confidence") -- backwards
#      per corrective_waves.py's own documented warning that combinations are
#      "the most subjective corrections... frequently a catch-all fitted in
#      hindsight": MORE chained joints means MORE opportunities for a
#      coincidental fit, not fewer, so triple_three now earns LESS than
#      double_three, not more.
# Re-measured after this fix: complex corrections dropped to 21 of 70
# selected counts (30%) -- see the Task 5 response's "Benchmark" section for
# the full before/after comparison.
#
# TRIANGLE completion RECALIBRATED (Task 5 Improvement, 2026-07-26): the
# original 0.9 ("comparable to a complete impulse, since detect_triangle
# only ever returns a fully-formed 5-leg read") was measured across 15
# dataset/timeframe combinations (ES/NQ/SPY x 5m/15m/1h/4h/1d, 3259 real
# candidates) and found to cause exactly the "false dominance" a single-
# instrument audit couldn't see: triangle's raw QUALITY is the LOWEST of
# all four corrective/motive types (median 0.37 vs. 0.56-0.59 for double/
# triple three, 0.58 for diagonal) -- detect_triangle's own shape check is
# real but coarse, and a genuine triangle's trendline convergence rarely
# measures as cleanly as a combination's retracement ratio does -- yet
# triangle WON selection 72.6% of the time it was generated, dwarfing
# combo (14.6%), impulse (34.6%, matching its 34.4% share of the pool
# almost exactly -- i.e. fair), and diagonal (44.1%). The 0.9 completion
# bonus was masking triangle's weaker measured fit with the largest
# completion credit of any corrective type. Lowered to 0.55 -- matching
# _DIAGONAL_COMPLETION_BONUS below, since both are single, well-defined,
# always-fully-formed-or-nothing shapes with comparable epistemic status,
# unlike combinations' inherent subjectivity -- which brings triangle's
# median final score in line with the other three types instead of
# systematically outscoring them. See the Task 5 Improvement response for
# the full before/after win-rate table.
_CORRECTIVE_COMPLETION_BONUS = {"triangle": 0.55, "double_three": 0.35, "triple_three": 0.25}

# Half of impulse's _SIZE_WEIGHT (0.5) -- see calibration note above, cause 1.
_CORRECTIVE_SIZE_WEIGHT = 0.25


def _score_corrective_candidate(cand: CorrectiveCandidate, swings: List[Swing],
                                total_span: int) -> float:
    """Composite score for a triangle/complex-correction candidate, built on
    the SAME three ingredients _score_candidate uses for impulses (fit
    quality, a completion bonus, a size bonus) so the two candidate types
    land on a comparable scale and _select_best_counts's unmodified DP can
    weigh them fairly against each other (Task 5, requirement 4) -- NOT a
    modification of _score_candidate itself, which stays impulse-only. Uses
    _CORRECTIVE_SIZE_WEIGHT, not _SIZE_WEIGHT -- see that constant's comment.
    """
    span = swings[cand.end_pos].index - swings[cand.start_pos].index
    size = min(span / total_span, 1.0) if total_span > 0 else 0.0
    completion = _CORRECTIVE_COMPLETION_BONUS[cand.kind]
    return round(cand.quality + completion + _CORRECTIVE_SIZE_WEIGHT * size, 3)


# Task 6: comparable completion/size treatment for diagonal candidates,
# calibrated against real data the same way Task 5's corrective constants
# were (see that constant's comment for why guessing without measuring is
# unreliable). A diagonal is only ever returned by find_diagonal_candidates
# as a fully-formed 5-leg wedge (no partial-diagonal concept), so its base
# completion is comparable to a complete impulse/triangle -- but diagonals
# are widely regarded (including by Prechter) as the most subjective,
# least rule-rigid Elliott pattern, and this module's own quality check is
# a heuristic wedge-monotonicity read, not a hard-rule validator the way
# _grow_count is for impulses -- so completion starts LOWER than a
# triangle's, and the recursive subdivision_bonus (0 when unavailable) is
# folded in directly rather than treated as a mere tie-breaker, since it is
# the only genuine (non-heuristic) internal-structure check available here.
_DIAGONAL_COMPLETION_BONUS = 0.55
_DIAGONAL_SIZE_WEIGHT = 0.25


def _score_diagonal_candidate(cand: DiagonalCandidate, swings: List[Swing],
                              total_span: int) -> float:
    """Composite score for a diagonal candidate -- fit quality + recursive
    subdivision bonus + a completion bonus + a size bonus, on a scale
    comparable to impulse/corrective scores (Task 6 requirement: "produce
    candidates in the same format ... so the existing scoring engine can
    compare them fairly"). NOT a modification of _score_candidate or
    _score_corrective_candidate, which are untouched.
    """
    span = swings[cand.end_pos].index - swings[cand.start_pos].index
    size = min(span / total_span, 1.0) if total_span > 0 else 0.0
    fit = 0.7 * cand.quality + 0.3 * cand.subdivision_bonus
    return round(fit + _DIAGONAL_COMPLETION_BONUS + _DIAGONAL_SIZE_WEIGHT * size, 3)


@dataclass
class _Candidate:
    labels: List[WaveLabel]
    start_index: int    # swing index of this candidate's Wave 1
    end_index: int       # swing index of its last labeled point
    warnings: List[str]
    score: float


def _generate_candidates(swings: List[Swing], rsi: Optional[pd.Series]
                         ) -> tuple[List[_Candidate], bool]:
    """UNIFIED candidate generation (Task 7, 2026-07-24) -- ONE pass over
    swing positions, routed by the PRE-NUMBERING structural classifier
    (structure_classification.classify_structure_detailed), which now
    scores ALL FIVE detectable hypotheses (impulse, correction, triangle,
    complex correction, diagonal) together and picks the single best one
    per position -- replacing Tasks 5-6's four independent, uncoordinated
    scans (impulse gate + unconditional triangle scan + unconditional
    combination scan + unconditional diagonal scan) that never consulted
    each other or the classifier.

    Design (see structure_classification.py's "Unified routing" docstring
    section for the classifier side of this):
      1. Run complex_corrections.find_triangle_candidates /
         find_complex_correction_candidates / diagonal_waves.
         find_diagonal_candidates EXACTLY ONCE each, UNCHANGED (still O(n)
         full-series scans -- these are NOT reimplemented, only INDEXED by
         their own origin position instead of unconditionally accepted).
      2. For every swing position, classify_structure_detailed scores
         impulse/correction/sideways (its own existing, unchanged signals)
         together with whichever triangle/combo/diagonal candidate (if any)
         has its origin AT this exact position, and returns the winner PLUS
         the winning candidate object itself (``winner_detail`` -- so the
         winning detector's result is reused, never recomputed).
      3. Exactly ONE detector's output is used per position: TRENDING_IMPULSE
         -> ``_grow_count`` (unchanged); POTENTIAL_TRIANGLE/
         POTENTIAL_COMPLEX_CORRECTION/POTENTIAL_DIAGONAL -> the already-
         computed candidate from step 1, unpacked into a ``_Candidate`` the
         SAME way Tasks 5-6 already did; anything else -> nothing attempted
         at this position.
    ``_grow_count``'s own hard rules, ``_score_candidate``/
    ``_score_corrective_candidate``/``_score_diagonal_candidate``'s scoring,
    and ``_select_best_counts``'s selection are all UNCHANGED (Task 7,
    requirement 4) -- only WHICH detector gets a turn at each position
    changed, not what any detector does once it's given one, and not how
    candidates are scored or selected afterward.

    Returns ``(candidates, any_attempted)`` -- ``any_attempted`` is False
    only when EVERY single index was routed to something other than
    TRENDING_IMPULSE, i.e. nothing in the whole series ever looked like the
    best explanation was starting an impulse there; the caller uses this to
    report "No valid impulse structure." rather than silently returning an
    empty count. Unchanged in meaning from before Task 7 -- it does NOT
    track triangle/combo/diagonal attempts, since the existing warning text
    is specifically about impulses.
    """
    total_span = swings[-1].index - swings[0].index if swings else 0

    # Step 1: unchanged O(n) scans, now consumed by position instead of
    # unconditionally accepted.
    triangle_by_origin = {c.start_pos: c for c in find_triangle_candidates(swings)}
    combo_by_origin = {c.start_pos: c for c in find_complex_correction_candidates(swings)}
    diagonal_by_origin = {c.start_pos: c for c in find_diagonal_candidates(swings)}

    out: List[_Candidate] = []
    any_attempted = False
    for i in range(1, len(swings)):
        direction: Direction = "up" if swings[i].kind == SwingType.HIGH else "down"
        origin_pos = i - 1
        decision = classify_structure_detailed(
            swings, i, direction,
            triangle=triangle_by_origin.get(origin_pos),
            combo=combo_by_origin.get(origin_pos),
            diagonal=diagonal_by_origin.get(origin_pos),
        )

        if decision.winner == StructureType.TRENDING_IMPULSE:
            any_attempted = True
            result = _grow_count(swings, i, rsi)
            if result is None:
                continue
            labels, next_i, warnings = result
            out.append(_Candidate(
                labels=labels, start_index=i, end_index=next_i - 1,
                warnings=warnings, score=_score_candidate(labels, total_span),
            ))

        elif decision.winner == StructureType.POTENTIAL_TRIANGLE:
            cand = decision.winner_detail   # CorrectiveCandidate -- see _route_detail
            labels = [WaveLabel(swing=sw, wave=lab, sub=None, direction=cand.correction.direction)
                     for lab, sw in cand.boundary]
            out.append(_Candidate(
                labels=labels, start_index=cand.start_pos, end_index=cand.end_pos,
                warnings=[], score=_score_corrective_candidate(cand, swings, total_span),
            ))

        elif decision.winner == StructureType.POTENTIAL_COMPLEX_CORRECTION:
            cand = decision.winner_detail   # CorrectiveCandidate
            labels = [WaveLabel(swing=sw, wave=lab, sub=None, direction=cand.correction.direction)
                     for lab, sw in cand.boundary]
            out.append(_Candidate(
                labels=labels, start_index=cand.start_pos, end_index=cand.end_pos,
                warnings=[], score=_score_corrective_candidate(cand, swings, total_span),
            ))

        elif decision.winner == StructureType.POTENTIAL_DIAGONAL:
            dcand = decision.winner_detail   # DiagonalCandidate
            dlabels = [WaveLabel(swing=p, wave=w, sub=None, direction=dcand.direction)
                      for w, p in zip(("1", "2", "3", "4", "5"), dcand.pivots[1:])]
            out.append(_Candidate(
                labels=dlabels, start_index=dcand.start_pos, end_index=dcand.end_pos,
                warnings=[], score=_score_diagonal_candidate(dcand, swings, total_span),
            ))

        # POTENTIAL_CORRECTION / SIDEWAYS / UNKNOWN -- nothing attempted at
        # this position, matching the pre-Task-7 impulse-only gate's own
        # "don't seed here" behavior, now generalized to all four detectors.

    return out, any_attempted


def _select_best_counts(candidates: List[_Candidate],
                        n_swings: int) -> tuple[List[_Candidate], List[str]]:
    """Weighted interval scheduling over swing-index spans: choose the
    subset of NON-OVERLAPPING candidates that maximizes total NET score
    (each candidate's quality score minus _FRAGMENTATION_PENALTY -- see
    that constant's comment for why the penalty is required, not optional).
    Classic resource-scheduling DP; O(n + candidates) here since swing
    indices are already a dense integer sequence, so no binary search is
    needed -- for each position k, dp[k] is either "don't use any candidate
    ending here" (dp[k-1]) or "use one that does" (its net score + the best
    achievable before its own start).
    """
    by_end: dict[int, List[_Candidate]] = {}
    for c in candidates:
        by_end.setdefault(c.end_index, []).append(c)

    dp = [0.0] * (n_swings + 1)
    choice: List[Optional[_Candidate]] = [None] * (n_swings + 1)
    for k in range(1, n_swings + 1):
        dp[k] = dp[k - 1]
        for c in by_end.get(k - 1, []):
            total = (c.score - _FRAGMENTATION_PENALTY) + dp[c.start_index]
            if total > dp[k]:
                dp[k] = total
                choice[k] = c

    selected: List[_Candidate] = []
    k = n_swings
    while k > 0:
        c = choice[k]
        if c is None:
            k -= 1
        else:
            selected.append(c)
            k = c.start_index
    selected.reverse()

    # Runners-up: a candidate that lost is compared against the TOTAL net
    # score of every selected candidate it overlaps, not just one of them --
    # a single big rival often loses to several smaller selected counts
    # whose combined score beats it even though its own raw score looks
    # higher than any ONE of them individually (confirmed on real data:
    # a bars-1532-1686 candidate scoring 1.97 lost to three selected counts
    # -- 1.30, 1.05, 1.84 -- whose combined net (1.49) beat its own net
    # (1.07); comparing it against just the 1.05 one would have wrongly
    # implied it was the stronger read). Surfaced only if genuinely close
    # (within 90% of what it would have displaced) and itself reached at
    # least Wave 3, capped to the handful of stretches where it came
    # closest -- "lower-confidence counts should appear only as
    # alternates," not flood the primary read with every also-ran.
    ALT_SCORE_THRESHOLD = 0.9
    ALT_CAP = 5
    selected_ids = {id(c) for c in selected}
    ranked_alternates: List[tuple[float, str]] = []
    for c in candidates:
        if id(c) in selected_ids or len(c.labels) < 3:
            continue
        overlapping = [s for s in selected
                      if c.start_index < s.end_index and c.end_index > s.start_index]
        if not overlapping:
            continue
        swap_cost = sum(s.score - _FRAGMENTATION_PENALTY for s in overlapping)
        rival_net = c.score - _FRAGMENTATION_PENALTY
        closeness = rival_net / swap_cost if swap_cost > 0 else 0.0
        if closeness >= ALT_SCORE_THRESHOLD:
            w1, w_last = c.labels[0], c.labels[-1]
            plural = "count" if len(overlapping) == 1 else f"{len(overlapping)} counts"
            ranked_alternates.append((closeness, (
                f"Alternate {w1.direction}-count near bars {w1.index}-{w_last.index} "
                f"(reaches wave {w_last.wave}, confidence {c.score:.2f}) was considered, "
                f"but the {plural} chosen for this stretch scored more in total."
            )))
    ranked_alternates.sort(key=lambda pair: pair[0], reverse=True)
    alternates = [text for _, text in ranked_alternates[:ALT_CAP]]
    return selected, alternates


# --------------------------------------------------------------------------- #
# Driver: generate every candidate, then pick the highest-scoring
# non-overlapping set instead of walking left-to-right and keeping whichever
# one is found first (see module docstring, "Selection rewrite 2026-07-18").
# --------------------------------------------------------------------------- #
def label_wave_sequence(swings: List[Swing],
                        rsi: Optional[pd.Series] = None
                        ) -> tuple[List[WaveLabel], List[str], List[str]]:
    """Find the highest-confidence, non-overlapping set of Elliott wave
    counts across the whole swing series.

    ``rsi`` (optional): position-indexed RSI series (same bar-index space as
    the swings, e.g. ``identify_swings(df, ...)`` + ``calc_rsi(df['close'])``
    with the same reset index) used to gate Wave 5 on momentum divergence.

    Returns ``(labels, warnings, alternates)``:
      - ``warnings``: one message per selected count that stopped at a
        partial 1-2-3-4 specifically because Wave 5's momentum divergence
        couldn't be evaluated (RSI unavailable) -- PLUS, per explicit
        requirement, a single literal "No valid impulse structure." entry
        when the pre-numbering structural classifier rejected every swing
        index in the series (nothing ever looked like the start of a
        trending impulse), so this stretch was never even offered to
        ``_grow_count`` at all.
      - ``alternates``: one message per selected count that had a genuinely
        competitive (not just any) rival candidate covering the same
        stretch of chart, so a caller can show it wasn't the only
        reasonable reading.
    """
    candidates, any_attempted = _generate_candidates(swings, rsi)
    selected, alternates = _select_best_counts(candidates, len(swings))

    out: List[WaveLabel] = []
    warnings: List[str] = []
    if not any_attempted and len(swings) >= 2:
        warnings.append("No valid impulse structure.")
    for c in selected:
        out.extend(c.labels)
        warnings.extend(c.warnings)
    return out, warnings, alternates


# --------------------------------------------------------------------------- #
# Pretty print
# --------------------------------------------------------------------------- #
def describe_sequence(labels: List[WaveLabel]) -> str:
    return "\n".join(
        f"  bar {w.index:>3}  {w.direction:<4}  Wave {w.label:<5}  @ {w.price:.2f}"
        for w in labels
    )


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def _ohlc_from_pivots(pivots, bars_per_leg=8, noise=0.2, seed=1):
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed)
    closes = []
    for a, b in zip(pivots, pivots[1:]):
        closes.extend(np.linspace(a, b, bars_per_leg, endpoint=False))
    closes.append(pivots[-1])
    closes = np.asarray(closes) + rng.normal(0, noise, len(closes))
    high = closes + rng.uniform(0.1, 0.5, len(closes))
    low = closes - rng.uniform(0.1, 0.5, len(closes))
    return pd.DataFrame({"high": high, "low": low, "close": closes})


if __name__ == "__main__":
    # A clean 5-wave uptrend (100->140) followed by an a-b-c correction down
    # to 112, with a lead-in so the origin is a real fractal.
    pivots = [106, 100, 110, 104, 130, 118, 140, 122, 132, 112, 120]
    df = _ohlc_from_pivots(pivots, bars_per_leg=8, noise=0.2, seed=3)

    swings = identify_swings(df, left=2, right=2, min_move=3.0)
    print(f"{len(swings)} confirmed swings")

    sequence, warnings, alternates = label_wave_sequence(swings)
    print(f"\n{len(sequence)} labeled points:")
    print(describe_sequence(sequence))
    if warnings:
        print("\nwarnings:")
        for w in warnings:
            print(f"  - {w}")
    if alternates:
        print("\nalternates:")
        for a in alternates:
            print(f"  - {a}")
