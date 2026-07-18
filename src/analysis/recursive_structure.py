"""
recursive_structure.py
=======================

Generic, DETECTOR-AGNOSTIC recursive structural verification -- the engine
behind "does this window of price action genuinely subdivide the way this
hypothesis claims, not just resemble it at a glance."

Why a separate module, not folded into structure_classification.py
----------------------------------------------------------------------
Per explicit requirement (Task 4, item 5): "Design the recursion so every
detector can reuse it later... without duplicate logic." The recursion,
depth/swing/confidence stopping conditions, and caching are ALL completely
independent of WHAT is being verified -- only the DETECTOR (a plain
callback: swings -> DetectorResult|None) differs between an impulse check,
a zigzag/flat check, a future triangle check, a future combination check,
or a future diagonal check. Keeping this machinery here means adding a new
detector later is a new small function plus a call to
``verify_recursive_structure`` -- never a copy of the recursion itself.
This module has ZERO knowledge of Elliott Wave rules, impulses, or
corrections -- it only knows how to re-detect swings in a bar range and
hand them to whatever detector it's given.

How verification works (TRUE decomposition, Task 3 Improvement 2026-07-25)
----------------------------------------------------------------------------
Given a bar range [bar_start, bar_end] in some price DataFrame:
  1. Re-detect swings WITHIN that range at a given (left, right, min_move)
     sensitivity -- finer than whatever produced the original candidate.
  2. Hand those swings to the DETECTOR -- a small, BOUNDED check (not an
     exhaustive scan of every possible start; that's what the top-level
     candidate generation already does) for whether this window plausibly
     contains the hypothesis's structure. The detector also reports which
     of ITS OWN sub-windows (e.g. an impulse's own wave legs) are worth
     examining one degree finer, and WHAT the structure resolved to
     (``resolved_type``, e.g. "impulse"/"triangle"/"double_three") -- this
     is a genuine identification, not just a pass/fail.
  3. If depth allows, recurse into EVERY sub-window with enough bars --
     not just the largest. "Verify wherever sufficient data exists" means
     every claimed leg gets its own independent, honest attempt. Bounded
     by the detector's own small leg count (at most ~5 for any pattern
     this codebase detects) and a small ``max_depth`` (1-2) -- see
     "Complexity" below for why this stays cheap despite branching.
  4. Confidence combines the current level's own detector confidence with
     a DECAYING bonus from the AVERAGE of its verified children's
     confidences (not just one) -- a structure where every leg
     independently verifies is a stronger decomposition than one where
     only its single largest leg does, even at equal top-level confidence.
  5. A miss at ANY level (bar range too short, too few re-detected swings,
     or no detector match above ``min_confidence``) reports
     ``confidence=0.0`` and ``resolved_type=None`` EXPLICITLY -- never a
     leaked, sub-threshold detector score. "Could not determine" and "weakly
     matched" are never conflated.

Stopping conditions (all three required by explicit instruction)
--------------------------------------------------------------------
  - max_depth: recursion never goes deeper than this, regardless of data.
  - min_swings: a window with fewer swings than this is never even
    re-detected/handed to the detector -- there's nothing to check.
  - min_confidence: a detector result below this bar doesn't count as
    "verified" and does not trigger further recursion into its sub-windows
    (no point examining the internals of a shape that wasn't a good match
    at this level to begin with).

Complexity
----------
Recursing into EVERY sub-window (not just the largest) makes the cost of
one top-level call O(branching ** max_depth) re-detections, each O(window
size) -- branching is bounded by the largest detector's own leg count
(triangle/diagonal: 5), and max_depth stays small (1-2), so worst case is
~5-30 re-detections per top-level call, not unbounded. See the module's
companion benchmark and the Task 3 Improvement response's "Performance
impact" for measured real-data figures (cache hit rate matters far more
here than it did under the old single-path design, since siblings now
routinely probe overlapping finer windows).

Caching
-------
Real usage calls this once per CANDIDATE in wave_numbering's candidate
generation loop (hundreds per analysis), and nearby candidates' recursive
sub-windows routinely overlap -- more so now that every leg (not just the
largest) is explored. Results are memoized in a bounded, process-lifetime
LRU cache keyed on a cheap DataFrame identity fingerprint plus the
window/params -- see ``_cache_key`` for the exact fingerprint and its
accepted trade-offs.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

import pandas as pd

from .swing_identification import Swing, identify_swings


@dataclass
class DetectorResult:
    """What a pluggable detector reports about ONE window of swings."""
    valid: bool
    confidence: float                                             # 0..1
    sub_windows: List[Tuple[int, int]] = field(default_factory=list)  # bar ranges, LOCAL to this window
    label: str = ""


Detector = Callable[[List[Swing]], Optional[DetectorResult]]


@dataclass
class RecursiveVerification:
    verified: bool
    confidence: float
    depth_reached: int
    detector_label: str = ""
    # Task 3 Improvement (2026-07-25) -- what the detector determined this
    # window actually IS (e.g. "impulse", "triangle", "double_three",
    # "contracting_ending_diagonal") when verified, else None. None is the
    # EXPLICIT "could not determine" outcome required by that task's
    # requirement 5 -- confidence is ALWAYS 0.0 whenever this is None
    # (never a leaked, sub-threshold score that could be mistaken for a
    # partial finding). Additive field -- existing consumers reading only
    # .verified/.confidence/.depth_reached/.detector_label are unaffected.
    resolved_type: Optional[str] = None


# --------------------------------------------------------------------------- #
# Bounded LRU cache -- process-lifetime, shared across all callers/detectors.
# --------------------------------------------------------------------------- #
_CACHE: "OrderedDict[tuple, RecursiveVerification]" = OrderedDict()
# CALIBRATED against real data (Task 4 Improvement, 2026-07-26): measured
# directly with an unbounded cache, a single full wave_analysis.analyze()
# pass on the densest real dataset tested (ES 5m, 45 days, 8911 bars) touches
# 4389 UNIQUE cache keys -- already above the previous 4096 cap. That meant
# the cache was thrashing (evicting and recomputing) even within one cold
# run, not just failing to help on a second run -- confirmed by cache misses
# (4389) exceeding the old cap on that same single pass. Raised to 16384,
# ~3.7x the measured working set, so a single realistic analysis session
# doesn't self-evict, with headroom for denser data or multiple analyses
# sharing this process-lifetime cache. This is a pure cache-capacity fix,
# not a change to any recursion depth/confidence/swing threshold -- it does
# not loosen what counts as "verified," only how much verified work stays
# memoized.
_CACHE_MAX_SIZE = 16384
cache_stats = {"hits": 0, "misses": 0}


def _cache_key(df: pd.DataFrame, bar_start: int, bar_end: int, left: int, right: int,
              min_move: float, detector_name: str, depth: int) -> tuple:
    """Cache key uses a CHEAP DataFrame identity fingerprint (object id +
    length + first/last close), not a full content hash -- O(1) to compute,
    not O(window size), which matters since this runs on every candidate.

    Accepted trade-off: if two DIFFERENT DataFrame objects happened to
    share a reused id() (possible once the original is garbage-collected,
    over a long-running server's lifetime) AND identical length AND
    identical first/last close (a striking coincidence on top of that), a
    stale cache hit could return a wrong-but-plausible confidence score
    rather than crash. Low severity: this caches a CONFIDENCE SCORE that
    feeds into a larger weighted blend, not the wave count itself, and the
    coincidence required is vanishingly unlikely in practice.
    """
    n = len(df)
    first_close = float(df["close"].iloc[0]) if n and "close" in df.columns else 0.0
    last_close = float(df["close"].iloc[-1]) if n and "close" in df.columns else 0.0
    return (id(df), n, first_close, last_close, bar_start, bar_end,
           left, right, round(min_move, 6), detector_name, depth)


def _cache_get(key: tuple) -> Optional[RecursiveVerification]:
    if key in _CACHE:
        _CACHE.move_to_end(key)
        cache_stats["hits"] += 1
        return _CACHE[key]
    cache_stats["misses"] += 1
    return None


def _cache_put(key: tuple, value: RecursiveVerification) -> None:
    _CACHE[key] = value
    _CACHE.move_to_end(key)
    if len(_CACHE) > _CACHE_MAX_SIZE:
        _CACHE.popitem(last=False)


def clear_cache() -> None:
    """Exposed for tests/benchmarks that need a clean cache-hit-rate reading."""
    _CACHE.clear()
    cache_stats["hits"] = 0
    cache_stats["misses"] = 0


# --------------------------------------------------------------------------- #
# The recursion itself
# --------------------------------------------------------------------------- #
def verify_recursive_structure(
    df: pd.DataFrame,
    bar_start: int,
    bar_end: int,
    detector: Detector,
    detector_name: str,
    left: int = 2,
    right: int = 2,
    min_move: float = 0.0,
    depth: int = 0,
    max_depth: int = 2,
    min_swings: int = 5,
    min_confidence: float = 0.35,
    depth_decay: float = 0.5,
    finer_move_factor: float = 0.6,
) -> RecursiveVerification:
    """Verify whether [bar_start, bar_end] in ``df`` genuinely DECOMPOSES the
    way ``detector`` claims, recursing into EVERY internal leg with enough
    data (not just the largest) up to ``max_depth`` levels deeper. See
    module docstring for the full algorithm and stopping conditions.

    ``detector_name`` is a plain string used only for cache-key isolation
    (so differently-tuned callers on the identical window never collide)
    and diagnostics -- it carries no behavior of its own.

    Task 3 Improvement (2026-07-25) -- TRUE recursive decomposition, not
    just single-path validation: previously this recursed into exactly ONE
    (the largest) sub-window per level, which could confirm "this window
    subdivides reasonably" without ever actually checking most of the
    window's own claimed legs. Now every leg the detector reports (that has
    enough bars to be worth checking) is independently verified, and a
    parent's combined confidence reflects how its legs ACTUALLY resolved,
    not just its single largest one. Bounded, not exponential: branching
    factor is the detector's own leg count (at most ~5 for any pattern this
    codebase detects), and ``max_depth`` stays small (1-2), so total work
    per top-level call is O(branching ** max_depth) -- see the Task 3
    Improvement response's "Performance impact" for measured real-data
    figures. Per requirement 5 ("explicitly return UNKNOWN instead of
    assuming success"), failure ALWAYS reports ``confidence=0.0`` and
    ``resolved_type=None`` -- never a leaked, sub-threshold detector score
    that could be mistaken for a partial finding.
    """
    key = _cache_key(df, bar_start, bar_end, left, right, min_move, detector_name, depth)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    if bar_end - bar_start < min_swings:
        result = RecursiveVerification(False, 0.0, depth, detector_name, None)
        _cache_put(key, result)
        return result

    slice_df = df.iloc[bar_start:bar_end + 1].reset_index(drop=True)
    slice_swings = identify_swings(slice_df, left=left, right=right, min_move=min_move)
    if len(slice_swings) < min_swings:
        result = RecursiveVerification(False, 0.0, depth, detector_name, None)
        _cache_put(key, result)
        return result

    det_result = detector(slice_swings)
    if det_result is None or not det_result.valid or det_result.confidence < min_confidence:
        # Explicit UNKNOWN (requirement 5) -- confidence is 0.0 regardless
        # of whatever sub-threshold number a nearly-matching detector may
        # have computed internally; a miss is a miss, not "kind of."
        result = RecursiveVerification(False, 0.0, depth, detector_name, None)
        _cache_put(key, result)
        return result

    own_confidence = det_result.confidence
    resolved_type = det_result.label or None
    child_confidences: List[float] = []
    deepest = depth
    if depth < max_depth and det_result.sub_windows:
        # Recurse into EVERY leg with enough bars -- not just the largest.
        # "Verify wherever sufficient data exists" (requirement 2) means
        # every leg gets its own honest attempt, not just whichever one
        # happened to be biggest.
        candidates = [
            (bar_start + s, bar_start + e) for s, e in det_result.sub_windows
            if (bar_start + e) - (bar_start + s) >= min_swings
        ]
        for sub_start, sub_end in candidates:
            child = verify_recursive_structure(
                df, sub_start, sub_end, detector, detector_name,
                left=max(1, left - 1), right=max(1, right - 1),
                min_move=min_move * finer_move_factor,
                depth=depth + 1, max_depth=max_depth, min_swings=min_swings,
                min_confidence=min_confidence, depth_decay=depth_decay,
                finer_move_factor=finer_move_factor,
            )
            if child.verified:
                child_confidences.append(child.confidence)
                deepest = max(deepest, child.depth_reached)

    # A parent's decomposition bonus reflects how well ITS LEGS held up on
    # average, not just its single best (or only-tried) leg -- a structure
    # where only one of five legs verifies internally is a weaker
    # decomposition than one where all five do, even if that one leg's own
    # confidence is identical in both cases.
    child_bonus = depth_decay * (sum(child_confidences) / len(child_confidences)) if child_confidences else 0.0
    combined_confidence = min(1.0, round(own_confidence + child_bonus, 3))
    result = RecursiveVerification(True, combined_confidence, deepest, detector_name, resolved_type)
    _cache_put(key, result)
    return result
