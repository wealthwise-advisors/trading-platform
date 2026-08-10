"""
structure_classification.py
============================

Pre-numbering structural classification -- decides WHAT ELLIOTT STRUCTURE is
most likely beginning at a candidate point, BEFORE the wave numbering engine
is allowed to seed anything there.

History
-------
v1 (2026-07-19): asked "is this trending?" as a proxy for "is this an
impulse?". Approved-but-superseded design (2026-07-20): trend and Elliott
impulse are NOT the same thing -- many corrective structures trend strongly
(a sharp zigzag is *designed* to be efficient; running and expanded flats
routinely post large net displacement because B and/or C overshoot the prior
extreme). A pure momentum/efficiency filter would misclassify exactly the
corrective patterns most likely to look impulsive. Redesigned around a
structural-hypothesis question instead: "which of Elliott's known shapes
does this pivot sequence most resemble?"

v2 (2026-07-20): adds internal subdivision evidence. Before this,
POTENTIAL_IMPULSE vs. POTENTIAL_CORRECTION was still decided mostly by
net-progress/direction/reversal signals -- structurally an improvement over
v1's single "trending" gate, but still not asking the one question that
actually distinguishes an impulse from a correction in Frost & Prechter:
does the internal leg sequence subdivide like FIVE waves (motive: legs 1/3/5
bigger than the retracement legs 2/4, extending the trend each time) or like
THREE (corrective: one dominant retracement leg, no big/small alternation)?
``_subdivision_evidence()`` estimated this from the window's OWN
already-detected swings -- not a full recursive re-count, just a structural
leg-SIZE fingerprint. Marked explicitly PROVISIONAL at the time (see git
history / v2 note preserved below) pending genuine recursive verification.

v3 (2026-07-21, THIS module): replaces the provisional heuristic's role as
primary evidence with GENUINE RECURSIVE STRUCTURAL SUBDIVISION
(``recursive_structure.verify_recursive_structure``, a new detector-agnostic
engine -- see that module's docstring for the full recursion/caching
design). Instead of comparing leg SIZES, this actually re-runs swing
detection at a finer degree WITHIN the candidate window and checks whether
that finer data grows into a legal Wave 1-5 count (reusing
``wave_numbering._grow_count`` -- the SAME hard-rule engine real numbering
runs) or a genuine Start-A-B-C correction (reusing
``corrective_waves.classify_abc`` -- the SAME zigzag/flat classifier real
corrective labeling runs), recursing into the largest internal leg up to a
bounded depth. ``_subdivision_evidence`` is NOT deleted (per explicit
instruction) -- it is DEMOTED to a secondary/tie-breaking input, contributing
~10% of a hypothesis's confidence when recursive verification actually ran
(vs. its former ~25-35%), and only reverts to its old, larger weight as a
graceful degradation when no DataFrame context is available to recurse over
at all (see ``set_recursion_context`` -- e.g. this module's own ``__main__``
demo, which has no raw price data, only synthetic swings). See
"PROVISIONAL STATUS" below -- the migration promised there has now happened.

PROVISIONAL STATUS -- MIGRATED (v3, 2026-07-21): ``_subdivision_evidence``'s
leg-SIZE heuristic estimated "does this look like 5 waves or 3" -- it
estimated, it did not verify, and could be fooled (e.g. a corrective leg
that happens to be unusually large, or an impulse leg that happens to be
small, shifts the size ratio without changing what the structure actually
is). It has now been demoted exactly as promised: recursive verification
(``_impulse_recursive_detector`` / ``_correction_recursive_detector`` below,
built on ``recursive_structure.verify_recursive_structure``) is PRIMARY
evidence whenever a DataFrame context is available; ``_subdivision_evidence``
is SECONDARY (a tie-breaker/confidence nudge), never deleted, per explicit
instruction. ``_SUBDIVISION_EVIDENCE_PROVISIONAL`` (below) is now False --
the code-level marker matches this migration, not just the docstring.

v4 (2026-07-24, Task 7 -- UNIFIED ROUTING): closes the gap this module's own
v1-v3 docstrings kept flagging as a TODO: ``POTENTIAL_TRIANGLE``,
``POTENTIAL_COMPLEX_CORRECTION``, and ``POTENTIAL_DIAGONAL`` were named,
reserved hypotheses that always scored 0.0 -- real detectors existed
(``complex_corrections.py``, ``diagonal_waves.py``, added in Tasks 5-6) but
ran as FOUR independent, uncoordinated full-series scans in
``wave_numbering._generate_candidates`` that never consulted this
classifier or each other. This module is now the actual entry point:
``classify_structure_detailed`` accepts the (already-computed, by
``wave_numbering._generate_candidates`` -- see that module for the O(n)
precompute-then-route design) triangle/combination/diagonal candidate for
THIS position, if one exists there, and scores it as a real competing
hypothesis using ITS OWN quality (``CorrectiveCandidate.quality`` /
``DiagonalCandidate.quality``+``subdivision_bonus``) -- not a reimplemented
heuristic. The overall winner across ALL SEVEN hypotheses determines which
ONE detector's already-computed result ``_generate_candidates`` actually
uses (via the new ``winner_detail``/``sub_type`` fields on
``StructureConfidence``) -- no detector runs twice, and no detector's
result is used without having won the comparison. See "Unified routing"
below for the full design.

What this module does
----------------------
``classify_structure_detailed()`` returns a confidence score (0..1) for
EVERY hypothesis in ``StructureType`` at once, plus the winner. The plain
``classify_structure()`` (unchanged name and return type -- see "Backward
compatibility") is a thin wrapper returning just the winner, so
wave_numbering.py's existing call site needs zero changes.

Hypotheses (``StructureType``)
-------------------------------
  UNKNOWN                     -- too few swings to say anything at all
  POTENTIAL_IMPULSE           -- looks like the start of a 5-wave motive move
  POTENTIAL_CORRECTION        -- looks like a simple corrective retracement
  POTENTIAL_DIAGONAL          -- leading or ending diagonal (see ``sub_type``)
  POTENTIAL_TRIANGLE          -- contracting or expanding triangle (see ``sub_type``)
  POTENTIAL_COMPLEX_CORRECTION -- double three (WXY) or triple three (WXYXZ) (see ``sub_type``)
  SIDEWAYS                    -- no coherent shape or direction at all

TRIANGLE/COMPLEX_CORRECTION/DIAGONAL score 0.0 ONLY when no candidate was
found for that hypothesis at this position (the ``triangle``/``combo``/
``diagonal`` parameters below are ``None``) -- not unconditionally, as in
v1-v3. See "Unified routing" below.

Unified routing (v4)
------------------------
``classify_structure_detailed`` does not itself SCAN for triangles,
combinations, or diagonals -- that would duplicate ``complex_corrections.py``
/ ``diagonal_waves.py``'s own O(n) scans. Instead, ``wave_numbering.
_generate_candidates`` runs those scans ONCE (unchanged, full-series, O(n)
each), indexes each hit by its own origin position, and passes whichever
candidate (if any) exists at THIS position into this function. This
function's only new job is to SCORE that candidate as a genuine competing
hypothesis (using its own already-computed ``quality`` -- no recomputation)
against impulse/correction/sideways, and report which won via ``winner``
plus the winning candidate object itself via ``winner_detail`` (so
``_generate_candidates`` never re-runs detection for whichever hypothesis
wins -- see that module's docstring for the full loop). ``sub_type`` reports
the finer distinction the user-facing taxonomy asks for (contracting/
expanding triangle, double_three/triple_three, leading/ending diagonal)
without adding new ``StructureType`` enum members (backward compatibility --
see "Backward compatibility" below). Passing no candidates (the default)
reproduces v1-v3's behavior EXACTLY -- see "Backward compatibility".

Backward compatibility (why old names still exist)
----------------------------------------------------
The approved v2 taxonomy renames v1's ``TRENDING_IMPULSE`` ->
``POTENTIAL_IMPULSE`` and ``CORRECTIVE`` -> ``POTENTIAL_CORRECTION``.
wave_numbering.py's ``_generate_candidates`` references
``StructureType.TRENDING_IMPULSE`` directly, and per explicit requirement
this task must NOT modify wave_numbering.py. Python enum members with
identical values become ALIASES of each other, so ``TRENDING_IMPULSE`` and
``CORRECTIVE`` are kept as aliases of the new canonical names below --
``StructureType.TRENDING_IMPULSE is StructureType.POTENTIAL_IMPULSE`` is
``True``. wave_numbering.py's existing `!=` comparison works completely
unchanged; this file is the only one touched. ``TRANSITION`` (v1) has no
replacement in the approved 7-value taxonomy -- every candidate now routes
to whichever hypothesis scores highest, with the confidence score itself
conveying how strong or marginal that read is, rather than a separate
"ambiguous" bucket.

v4 (Task 7) backward compatibility: ``classify_structure_detailed`` and
``classify_structure`` both gained three new trailing KEYWORD-DEFAULTED
parameters (``triangle=None, combo=None, diagonal=None``). Any existing
call written the old way (positional ``swings, at_index, direction`` plus
optionally ``window``) is completely unaffected -- with all three left at
their default ``None``, every new score term evaluates to 0.0 exactly as
the old hardcoded ``_UNSUPPORTED`` loop did, so the impulse/correction/
sideways/unknown decision is BYTE-IDENTICAL to v3 for any caller that
doesn't pass the new arguments (verified -- see the Task 7 response's
"Regression verification"). ``StructureConfidence`` gained two new fields
(``winner_detail``, ``sub_type``), both defaulted, so existing code
constructing or reading a ``StructureConfidence`` without them is
unaffected.

Signals combined into every confidence score
-----------------------------------------------
  - recursive verification (PRIMARY when available): does this window's own
    finer-degree swings actually GROW into a legal Wave 1-5 count / a
    genuine Start-A-B-C correction? See "Recursive structural verification"
    below and ``recursive_structure.py``.
  - subdivision evidence (SECONDARY -- see "PROVISIONAL STATUS -- MIGRATED"
    above): does the window's leg sequence look 5-wave-like or 3-wave-like
    by SIZE alone? See ``_subdivision_evidence()``. Only ~10% weight when
    recursive verification ran; reverts to its old, larger weight only when
    no DataFrame context is available to recurse over.
  - swing progression: do the most recent same-kind pivots (HH/HL vs.
    LH/LL) agree with the hypothesis's implied direction?
  - structure persistence: how many times has the structure label flipped
    character within the window (few flips = a persistent, unbroken
    structure; many = noisy/unstable)?
  - momentum: is the most recent leg holding up in size relative to the
    rest of the window, or visibly petering out?
  - direction: net displacement and its sign across the window.

None of the above is a Fibonacci ratio -- per explicit requirement, this
module never gates on proximity to 0.618/0.382/etc. ``_subdivision_evidence``
compares average leg SIZES (motive legs vs. retracement legs), a structural
comparison, not a target-ratio check. Recursive verification does not gate on
Fibonacci ratios either -- it reuses the SAME hard-rule/classification
engines real wave numbering and corrective labeling already run.

Recursive structural verification (v3, superseded by v5 -- see below)
--------------------------------------------------------------------------
``classify_structure_detailed`` no longer takes only a DataFrame-free list
of swings at face value. When a DataFrame is available (opted in via
``set_recursion_context`` -- currently only ``wave_analysis.py`` does this,
wrapping its existing ``label_wave_sequence`` call; NOT wave_numbering.py,
which is unmodified), the window's own bar range is re-detected at a FINER
degree (one recursion level deeper each time, bounded by ``max_depth``) and
handed to a detector plugin. Stopping conditions (max recursion depth,
minimum swing count, minimum structure confidence) all live in
``recursive_structure.py``, not here.

v5 (2026-07-25, Task 3 Improvement -- TRUE recursive decomposition): v3's
TWO narrow plugins (impulse-only, simple-correction-only) are replaced by
ONE ``_unified_recursive_detector`` (below) that tries EVERY pattern this
codebase can detect -- impulse, zigzag/flat, triangle, double/triple three,
leading/ending diagonal -- reusing each pattern's ALREADY-EXISTING detector
(``wave_numbering._grow_count``, ``corrective_waves.classify_abc``/
``detect_triangle``/``find_combinations``, ``diagonal_waves.
_try_diagonal_shape``) and reports whichever genuinely resolves. This is
genuine DECOMPOSITION, not single-shape validation: ``recursive_structure.
verify_recursive_structure`` (also upgraded, same task) now recurses into
EVERY one of the winning pattern's own legs with enough data (not just the
largest), so a detected triangle's all-five A-E legs each get their own
recursive attempt, a detected impulse's every wave gets one, and so on.
A miss anywhere reports an EXPLICIT unknown (confidence 0.0, no
resolved_type) rather than a leaked partial score. Every hypothesis this
module scores -- including triangle/complex-correction/diagonal, which v3
never verified recursively at all -- now gets a genuine recursive
contribution when a DataFrame context is available. Both plugins are plain
``recursive_structure.Detector`` callables with zero duplicated recursion
logic in the ENGINE (unchanged) -- only the detector supplied to it changed.

Scope (subdivision evidence -- DEMOTED to a last-resort fallback, v5)
-----------------------------------------------------------------------
``_subdivision_evidence`` deliberately does NOT re-detect finer sub-pivots
from raw price data. It only re-examines the SAME swings already available
in the local window, asking whether their OWN leg-count and leg-size
pattern resembles a 5-wave or 3-wave shape -- a coarse fingerprint, never a
validated sub-count. As of v5, it contributes to a hypothesis's confidence
ONLY when no DataFrame context is available for genuine recursion at all
(previously it kept a small ~10% weight even alongside real recursion) --
requirement 3's "remove remaining heuristic subdivision decisions wherever
possible." The function and its exposed fields (``five_wave_evidence``/
``three_wave_evidence``) are kept, not deleted, for backward compatibility.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, TYPE_CHECKING

import pandas as pd

from .swing_identification import Swing, SwingType, StructureLabel
from .corrective_waves import classify_abc, detect_triangle, find_combinations, CorrectionType
from .recursive_structure import verify_recursive_structure, DetectorResult
from .complex_corrections import CorrectiveCandidate, _triangle_quality, _combination_quality

if TYPE_CHECKING:
    # Type-hint only -- diagonal_waves.py imports THIS module at its own top
    # level (to reuse the recursion-context accessor and detector plugins),
    # so a real, module-level import here would be circular. Safe under
    # TYPE_CHECKING/`from __future__ import annotations`: no runtime import
    # needed since classify_structure_detailed only ever receives an
    # already-constructed DiagonalCandidate and reads its attributes --
    # duck typing, not the class itself.
    from .diagonal_waves import DiagonalCandidate


class StructureType(str, Enum):
    UNKNOWN = "unknown"
    POTENTIAL_IMPULSE = "potential_impulse"
    POTENTIAL_CORRECTION = "potential_correction"
    POTENTIAL_DIAGONAL = "potential_diagonal"                 # reserved, not detected yet
    POTENTIAL_TRIANGLE = "potential_triangle"                 # reserved, not detected yet
    POTENTIAL_COMPLEX_CORRECTION = "potential_complex_correction"  # reserved, not detected yet
    SIDEWAYS = "sideways"

    # v1 names kept as ALIASES (same value = same enum member) purely so
    # wave_numbering.py's existing `StructureType.TRENDING_IMPULSE`
    # reference keeps working without that file being touched. Prefer the
    # canonical names above in any new code.
    TRENDING_IMPULSE = "potential_impulse"
    CORRECTIVE = "potential_correction"


# Fewer than this many swings in the window -> UNKNOWN, not a guess.
# 2 is the bare minimum (an origin plus one leg) -- see v1's regression
# note: a higher minimum rejected the canonical demo's true Wave 1 for
# having no history at the very start of a series, which can never exist.
MIN_WINDOW_SWINGS = 2
DEFAULT_WINDOW = 6

# Calibrated against real data (2026-07-20 sessions): measured net_progress
# across 452 real candidate windows (1yr ES 1h) -- median 0.23, p75 0.36.
NET_PROGRESS_TRENDING = 0.35
NET_PROGRESS_SIDEWAYS = 0.25
MIN_AMPLITUDE_RATIO = 0.4

# Below this winning confidence, don't commit to a specific hypothesis --
# fall back to SIDEWAYS (nothing scored convincingly).
MIN_WINNER_CONFIDENCE = 0.30

# MIGRATED away (v4, 2026-07-24, Task 7) -- TRIANGLE/COMPLEX_CORRECTION/
# DIAGONAL are no longer unconditionally scored 0.0; see
# classify_structure_detailed's triangle/combo/diagonal parameters and the
# module docstring's "Unified routing" section.

# MIGRATED (v3, 2026-07-21) -- see module docstring's "PROVISIONAL STATUS --
# MIGRATED" section. ``_subdivision_evidence()`` is now SECONDARY evidence
# only (a tie-breaker), not primary -- genuine recursive structural
# subdivision (below) has taken over the primary role whenever a DataFrame
# context is available. False here is a real, checkable marker that the
# migration described in the (now historical) v2 docstring note actually
# happened, not just prose.
_SUBDIVISION_EVIDENCE_PROVISIONAL = False

# Recursive verification tuning -- kept here (not buried in
# recursive_structure.py's generic defaults) so this call site's choices are
# visible and independently tunable. All three required stopping conditions
# (Task 4, item 2) are explicit, not implicit:
_RECURSION_MAX_DEPTH = 2          # never recurse deeper than 2 degrees finer
_RECURSION_MIN_SWINGS = 4         # a window with fewer bars/swings isn't worth re-detecting
_RECURSION_MIN_CONFIDENCE = 0.35  # a weak detector match doesn't count as "verified"

# Weight given to recursive verification. Task 3 Improvement (2026-07-25):
# the leg-SIZE subdivision heuristic is no longer given ANY weight once
# recursion actually ran (previously ~10%, a token weight from before the
# recursive engine covered all five hypothesis types) -- it only regains
# its original, larger weight as a last-resort fallback when there's no
# DataFrame context to recurse over at all (graceful degradation, e.g. this
# module's own synthetic-swings __main__ demo).
_RECURSIVE_WEIGHT = 0.45
_SUBDIVISION_WEIGHT_NO_RECURSION = {"impulse": 0.25, "correction": 0.35}


# --------------------------------------------------------------------------- #
# Ambient DataFrame context for recursive verification -- lets
# classify_structure()'s SIGNATURE stay exactly as it was (wave_numbering.py,
# its only caller, is explicitly protected and unmodified) while still
# giving classify_structure_detailed() access to raw price data when a
# caller that DOES have it (wave_analysis.py) opts in.
# --------------------------------------------------------------------------- #
_recursion_df_var: "contextvars.ContextVar[Optional[pd.DataFrame]]" = contextvars.ContextVar(
    "_recursion_df", default=None)


def set_recursion_context(df: pd.DataFrame) -> contextvars.Token:
    """Opt in to recursive structural verification for the current
    call context (thread/async-task) -- pair with ``reset_recursion_context``
    using the returned token, ideally in a try/finally. wave_numbering.py
    never calls this (it's outside this task's scope); wave_analysis.py's
    ``analyze()`` wraps its existing ``label_wave_sequence`` call with it so
    the live pipeline gets recursion "for free" without either file's
    signatures changing.
    """
    return _recursion_df_var.set(df)


def reset_recursion_context(token: contextvars.Token) -> None:
    _recursion_df_var.reset(token)


def get_recursion_context() -> Optional[pd.DataFrame]:
    """Public accessor for the ambient recursion DataFrame (Task 6) -- lets
    OTHER candidate-generation modules (currently only ``diagonal_waves.py``)
    reuse the SAME opt-in DataFrame and the SAME recursive verification
    plumbing this module already set up for Task 4, without reaching into
    the private ``_recursion_df_var`` directly. Returns ``None`` exactly
    when no caller has opted in via ``set_recursion_context`` -- callers
    must treat that as "no recursion available," not an error.
    """
    return _recursion_df_var.get()


# --------------------------------------------------------------------------- #
# Unified recursive detector (Task 3 Improvement, 2026-07-25) -- ONE
# detector callable, reused everywhere recursive verification happens
# (this module's own impulse/correction/triangle/complex-correction/
# diagonal confidence blending below, AND diagonal_waves.py's Wave-3
# subdivision check), replacing the two narrow, pattern-specific plugins
# (_impulse_recursive_detector / _correction_recursive_detector) Task 4
# built. Those two only ever asked "is this window impulse-shaped" or
# "is this window a simple ABC" -- never triangle, never a combination,
# never a diagonal, so recursion could confirm "yes, wave 3 subdivides
# into SOMETHING impulse-or-ABC-like" but could never actually identify a
# triangle or WXY hiding inside a leg. This detector tries EVERY pattern
# ``wave_numbering._generate_candidates`` can route to at the top level --
# genuine recursive DECOMPOSITION, not single-shape validation -- and
# reports whichever ACTUALLY resolves, reusing the SAME rule engines real
# numbering/labeling already run (requirement 4: no duplicate logic):
#   - impulse:            wave_numbering._grow_count (lazy import)
#   - zigzag/flat:        corrective_waves.classify_abc
#   - triangle:           corrective_waves.detect_triangle +
#                         complex_corrections._triangle_quality
#   - double/triple three: corrective_waves.find_combinations +
#                         complex_corrections._combination_quality
#   - leading/ending diagonal: diagonal_waves._try_diagonal_shape (lazy
#                         import -- the RECURSION-FREE variant, see that
#                         function's docstring for why: this detector runs
#                         FROM INSIDE a verify_recursive_structure call, so
#                         calling the full _try_diagonal (which itself
#                         starts a fresh, independent recursive check)
#                         would nest recursive_structure calls inside each
#                         other -- wasteful duplicate work, not infinite,
#                         but exactly the kind of duplication requirement 3
#                         asks to remove).
# Whichever pattern scores highest wins; if NONE validate, returns None,
# which verify_recursive_structure turns into an EXPLICIT unknown
# (confidence 0.0, resolved_type None) -- requirement 5, never an assumed
# partial success.
# --------------------------------------------------------------------------- #
_IMPULSE_DEPTH_CONFIDENCE = {2: 0.30, 3: 0.55, 4: 0.75, 5: 0.95}

# resolved_type strings the unified detector uses for a simple zigzag/flat
# read (CorrectionType.value for each of the four simple variants) -- used
# to route a recursive result back to POTENTIAL_CORRECTION's confidence.
_SIMPLE_CORRECTION_LABELS = {
    CorrectionType.ZIGZAG.value, CorrectionType.REGULAR_FLAT.value,
    CorrectionType.EXPANDED_FLAT.value, CorrectionType.RUNNING_FLAT.value,
}


def _simple_correction_confidence(corr) -> float:
    """How decisively a classify_abc() read's B/C ratios sit inside their
    matched category -- classify_abc always returns SOME category, so this
    is a confidence-in-the-read measure, not a pass/fail gate."""
    b = corr.metrics.get("b_retrace_of_A", 0.0)
    c = corr.metrics.get("c_beyond_A", 0.0)
    if corr.type == CorrectionType.ZIGZAG:
        return round(0.4 + 0.5 * max(0.0, min(1.0, 1.0 - b / 0.90)), 3)
    if corr.type == CorrectionType.REGULAR_FLAT:
        return round(0.4 + 0.5 * max(0.0, 1.0 - abs(b - 1.0) / 0.15), 3)
    return round(0.4 + 0.4 * max(0.0, min(1.0, c)), 3)   # EXPANDED_FLAT / RUNNING_FLAT


def _unified_recursive_detector(swings: List[Swing]) -> Optional[DetectorResult]:
    attempts: List[DetectorResult] = []

    # ---- impulse ----
    if len(swings) >= 3:
        from .wave_numbering import _grow_count  # lazy: avoids the module-level cycle
        result = _grow_count(swings, 1, None)
        if result is not None:
            labels, _next_i, _warnings = result
            highest = max((int(w.wave) for w in labels
                          if w.wave.isdigit() and int(w.wave) <= 5), default=1)
            points = [swings[0].index] + [w.index for w in labels]
            sub_windows = [(points[k], points[k + 1]) for k in range(len(points) - 1)
                          if points[k + 1] > points[k]]
            attempts.append(DetectorResult(
                valid=True, confidence=_IMPULSE_DEPTH_CONFIDENCE.get(highest, 0.2),
                sub_windows=sub_windows, label="impulse",
            ))

    # ---- simple correction (zigzag / flat variants) ----
    # sub_windows use each swing's OWN .index (already a LOCAL bar offset --
    # slice_swings come from a reset-index slice, per
    # verify_recursive_structure's "(bar_start + s, bar_start + e)" usage),
    # never a raw list position -- a real bug caught and fixed while
    # verifying this against real data (see Task 3 Improvement response,
    # "Regression verification").
    if len(swings) >= 4:
        corr = classify_abc(swings[:4])
        sub_windows = [(s.index, e.index) for s, e in
                       ((swings[0], swings[1]), (swings[1], swings[2]), (swings[2], swings[3]))
                       if e.index > s.index]
        attempts.append(DetectorResult(
            valid=True, confidence=_simple_correction_confidence(corr),
            sub_windows=sub_windows, label=corr.type.value,
        ))

    # ---- triangle ----
    if len(swings) >= 6:
        tri = detect_triangle(swings[:6])
        if tri is not None:
            sub_windows = [(tri.pivots[k].index, tri.pivots[k + 1].index) for k in range(5)]   # legs a..e, ALL five
            attempts.append(DetectorResult(
                valid=True, confidence=_triangle_quality(tri),
                sub_windows=sub_windows, label="triangle",
            ))

    # ---- double / triple three (complex correction) ----
    if len(swings) >= 8:
        combos = [c for c in find_combinations(swings) if c.pivots[0] is swings[0]]
        if combos:
            combo = max(combos, key=lambda c: len(c.pivots))   # prefer triple over double if both fit
            p = combo.pivots
            boundaries = [0, 3, 4, 7] if len(p) == 8 else [0, 3, 4, 7, 8, 11]
            sub_windows = [(p[boundaries[k]].index, p[boundaries[k + 1]].index)
                          for k in range(len(boundaries) - 1)]
            attempts.append(DetectorResult(
                valid=True, confidence=_combination_quality(combo),
                sub_windows=sub_windows, label=combo.type.value,
            ))

    # ---- leading / ending diagonal ----
    if len(swings) >= 6:
        from .diagonal_waves import _try_diagonal_shape  # lazy: avoids nested recursion, see that function's docstring
        dcand = _try_diagonal_shape(swings, 1)
        if dcand is not None:
            sub_windows = [(dcand.pivots[k].index, dcand.pivots[k + 1].index) for k in range(5)]   # legs 1..5, ALL five
            attempts.append(DetectorResult(
                valid=True, confidence=dcand.quality,
                sub_windows=sub_windows, label=f"{dcand.shape}_{dcand.position}_diagonal",
            ))

    if not attempts:
        return None
    return max(attempts, key=lambda a: a.confidence)


@dataclass
class StructureConfidence:
    """Confidence score (0..1) for EVERY hypothesis at once -- not just the
    winner -- so a caller (or a test) can see how close a call was, not
    just which label won."""
    scores: Dict[StructureType, float]
    winner: StructureType
    winner_confidence: float
    five_wave_evidence: float = 0.0
    three_wave_evidence: float = 0.0
    # Task 7 (v4) -- the ALREADY-COMPUTED candidate object backing the
    # winner, when the winner is TRIANGLE/COMPLEX_CORRECTION/DIAGONAL and a
    # candidate was actually passed in (None otherwise, including whenever
    # the winner is IMPULSE/CORRECTION/SIDEWAYS/UNKNOWN) -- lets
    # wave_numbering._generate_candidates use the winning detector's result
    # directly instead of re-running detection. sub_type is the finer
    # distinction ("contracting"/"expanding", "double_three"/"triple_three",
    # "contracting_leading"/"contracting_ending"/etc.) without adding new
    # StructureType enum members.
    winner_detail: Optional[object] = None
    sub_type: Optional[str] = None


def _label_sequence(window: List[Swing]) -> List[Optional[StructureLabel]]:
    """Re-derive HH/HL/LH/LL labels LOCALLY within this window only --
    deliberately not reusing whatever global label a swing already carries,
    since a pivot's HH/LH status depends on what window it's judged against.
    """
    labels: List[Optional[StructureLabel]] = []
    last_high: Optional[float] = None
    last_low: Optional[float] = None
    for s in window:
        if s.kind == SwingType.HIGH:
            labels.append(None if last_high is None
                         else (StructureLabel.HH if s.price > last_high else StructureLabel.LH))
            last_high = s.price
        else:
            labels.append(None if last_low is None
                         else (StructureLabel.HL if s.price > last_low else StructureLabel.LL))
            last_low = s.price
    return labels


def _subdivision_evidence(seg: List[Swing]) -> tuple[float, float]:
    """PROVISIONAL (Version 1) -- see module docstring, "PROVISIONAL STATUS"
    and ``_SUBDIVISION_EVIDENCE_PROVISIONAL``. This is a coarse leg-SIZE
    heuristic standing in for genuine recursive structural subdivision; it
    estimates a shape resemblance, it does not verify one. Expected to be
    demoted to a secondary/tie-breaking signal or removed outright once
    real recursive subdivision is implemented -- do not extend this
    function's heuristics further as a substitute for that real work.

    Estimate (five_wave_score, three_wave_score), each 0..1, from the
    window's OWN leg sequence -- see module docstring, "Scope".

    Five-wave (motive) fingerprint: Elliott's own rule is that waves 1, 3,
    5 are the trend-extending legs and 2, 4 are retracements -- so a real
    5-wave sequence should show the odd-position legs averaging LARGER
    than the even-position ones, across close to 5 legs total. This is a
    SIZE comparison (average motive leg vs. average retracement leg), not
    a Fibonacci ratio check against a specific target like 0.618.

    Three-wave (corrective) fingerprint: a clean A-B-C has exactly one
    dominant retracement (B) sitting between two other legs, with no
    big/small alternation pattern -- fewer legs, and B typically a
    substantial-but-partial fraction of A (not negligible, not so large it
    reads as an impulse's own wave 2).
    """
    legs = [abs(seg[i].price - seg[i - 1].price) for i in range(1, len(seg))]
    n = len(legs)

    five_wave = 0.0
    if n >= 4:
        motive_legs = legs[0::2]          # legs 1, 3, 5, ... (0-indexed 0, 2, 4)
        retracement_legs = legs[1::2]     # legs 2, 4, ...    (0-indexed 1, 3)
        if retracement_legs:
            avg_motive = sum(motive_legs) / len(motive_legs)
            avg_retracement = sum(retracement_legs) / len(retracement_legs)
            size_score = min(avg_motive / avg_retracement, 3.0) / 3.0 if avg_retracement > 0 else 0.0
            length_score = min(n / 5.0, 1.0)   # reward having close to 5 legs available
            five_wave = round(0.65 * size_score + 0.35 * length_score, 3)

    three_wave = 0.0
    if 2 <= n <= 3:
        a_leg, b_leg = legs[0], legs[1]
        b_ratio = (b_leg / a_leg) if a_leg > 0 else 0.0
        # peaks when B retraces a substantial-but-partial fraction of A
        # (~60%), tapering off toward either extreme -- a crude structural
        # proxy, not a Fibonacci gate (no specific ratio is required to
        # pass/fail, just rewarded when closer to a typical retracement).
        three_wave = round(max(0.0, 1.0 - abs(b_ratio - 0.6) / 0.6), 3)

    return five_wave, three_wave


# CALIBRATED against real data (2026-07-24, 1yr ES 1h -- same discipline as
# Task 5's NET_PROGRESS_TRENDING/_CORRECTIVE_COMPLETION_BONUS fixes): a
# first pass comparing triangle.quality / combo.quality / diagonal's blended
# quality DIRECTLY (no rescaling) measurably starved triangles -- 7 of 85
# selected counts before this fix, 0 of 71 after, on the identical dataset.
# Root cause: each detector's quality FORMULA has its own natural range,
# never calibrated against the others because each was built (Tasks 5-6) to
# compete only within its own independent scan, never head-to-head against
# a different detector's numbers. Measured medians: triangle 0.38, complex
# correction (double+triple three combined) 0.55, diagonal's blended
# (0.7*quality+0.3*subdivision_bonus) value 0.42 -- triangle's formula is
# structurally incapable of reaching combo's typical range at all (observed
# max 0.46 across 17 real candidates). Each is rescaled here so ITS OWN
# measured median maps to a common target confidence (0.5) -- "how good is
# this read FOR its own pattern type" rather than raw, incomparable
# formula output. This does NOT touch complex_corrections.py's or
# diagonal_waves.py's quality functions (unchanged, per requirement 4's
# spirit of not touching detector internals) or wave_numbering.py's
# downstream scoring (explicitly protected) -- it only affects which
# hypothesis WINS the classification step.
_TRIANGLE_TYPICAL_QUALITY = 0.38
_COMBO_TYPICAL_QUALITY = 0.55
_DIAGONAL_TYPICAL_BLENDED = 0.42
_CALIBRATION_TARGET = 0.5


def _route_detail(winner: StructureType,
                  triangle: Optional["CorrectiveCandidate"],
                  combo: Optional["CorrectiveCandidate"],
                  diagonal: Optional["DiagonalCandidate"]) -> tuple[Optional[object], Optional[str]]:
    """(winner_detail, sub_type) for whichever hypothesis actually won --
    None, None for anything that isn't TRIANGLE/COMPLEX_CORRECTION/DIAGONAL,
    or for one of those that DID win the label but had no candidate passed
    in (can't happen in practice -- a None candidate always scores 0.0, so
    it can only "win" by every other hypothesis also scoring 0.0, in which
    case MIN_WINNER_CONFIDENCE's fallback already redirects the winner
    elsewhere -- checked defensively anyway rather than assumed).
    """
    if winner == StructureType.POTENTIAL_TRIANGLE and triangle is not None:
        return triangle, triangle.correction.metrics.get("shape")
    if winner == StructureType.POTENTIAL_COMPLEX_CORRECTION and combo is not None:
        return combo, combo.kind
    if winner == StructureType.POTENTIAL_DIAGONAL and diagonal is not None:
        return diagonal, f"{diagonal.shape}_{diagonal.position}"
    return None, None


def classify_structure_detailed(swings: List[Swing], at_index: int, direction: str,
                                window: int = DEFAULT_WINDOW,
                                triangle: Optional["CorrectiveCandidate"] = None,
                                combo: Optional["CorrectiveCandidate"] = None,
                                diagonal: Optional["DiagonalCandidate"] = None) -> StructureConfidence:
    """Score every StructureType hypothesis for the window ending at
    ``swings[at_index]``, judged against the proposed ``direction``
    ("up"/"down"). This is the real algorithm; ``classify_structure()``
    below is a thin backward-compatible wrapper around it.

    ``triangle``/``combo``/``diagonal`` (Task 7, all optional, default
    ``None``): the ALREADY-COMPUTED candidate for THIS position, if
    ``wave_numbering._generate_candidates``'s own (unchanged)
    ``complex_corrections``/``diagonal_waves`` scans found one starting
    here -- see module docstring, "Unified routing". Passing none of them
    (the default) reproduces the pre-Task-7 behavior for these three
    hypotheses exactly (always 0.0) -- see "Backward compatibility".
    """
    # See "CALIBRATED against real data" note above _route_detail for why
    # this is a rescaled value, not raw .quality.
    triangle_base = (round(min(1.0, triangle.quality * (_CALIBRATION_TARGET / _TRIANGLE_TYPICAL_QUALITY)), 3)
                     if triangle is not None else 0.0)
    combo_base = (round(min(1.0, combo.quality * (_CALIBRATION_TARGET / _COMBO_TYPICAL_QUALITY)), 3)
                 if combo is not None else 0.0)
    diagonal_base = (round(min(1.0, (0.7 * diagonal.quality + 0.3 * diagonal.subdivision_bonus)
                              * (_CALIBRATION_TARGET / _DIAGONAL_TYPICAL_BLENDED)), 3)
                     if diagonal is not None else 0.0)

    # ---- Task 3 Improvement: recursive verification of the CANDIDATE'S
    # OWN span (not the backward look-back window used for impulse/
    # correction below) -- triangle/combo/diagonal, unlike impulse/
    # correction, already have concrete pivots at classification time
    # (precomputed by wave_numbering._generate_candidates' Step 1), so
    # "verify its own internal structure" (requirement 2) means checking
    # THAT exact span: re-detect swings within it at a finer degree and see
    # whether the SAME unified detector, run recursively over its own legs,
    # confirms it. At most one of triangle/combo/diagonal is non-None at
    # any position (Tasks 5-6's own design), so this is at most one extra
    # recursive call per position, not three. ----
    triangle_recursive = combo_recursive = diagonal_recursive = 0.0
    triangle_attempted = combo_attempted = diagonal_attempted = False
    _own_cand = triangle or combo or diagonal
    if _own_cand is not None:
        _recursive_df_for_own = _recursion_df_var.get()
        if _recursive_df_for_own is not None:
            _pivots = _own_cand.correction.pivots if hasattr(_own_cand, "correction") else _own_cand.pivots
            _own_bar_start, _own_bar_end = _pivots[0].index, _pivots[-1].index
            if _own_bar_end - _own_bar_start >= _RECURSION_MIN_SWINGS:
                _rv_own = verify_recursive_structure(
                    _recursive_df_for_own, _own_bar_start, _own_bar_end, _unified_recursive_detector, "unified",
                    max_depth=_RECURSION_MAX_DEPTH, min_swings=_RECURSION_MIN_SWINGS,
                    min_confidence=_RECURSION_MIN_CONFIDENCE,
                )
                _own_conf = _rv_own.confidence if _rv_own.verified else 0.0
                if _own_cand is triangle:
                    triangle_recursive, triangle_attempted = _own_conf, True
                elif _own_cand is combo:
                    combo_recursive, combo_attempted = _own_conf, True
                else:
                    diagonal_recursive, diagonal_attempted = _own_conf, True

    # Blend base (calibrated quality) with the recursive contribution --
    # SECONDARY weight (0.3), lower than impulse/correction's PRIMARY 0.45,
    # since the base value here is already a real, rule-validated
    # structural fit (not a heuristic proxy like net_progress/momentum),
    # so recursion nudges rather than dominates. Falls back to the base
    # value alone (no haircut) when recursion wasn't attempted at all
    # (no DataFrame context, or the span was too short) -- a genuine miss
    # (attempted but didn't verify) IS reflected as a 0.0 contribution,
    # same as everywhere else recursion is used in this module.
    _STRUCTURE_RECURSIVE_WEIGHT = 0.3
    triangle_confidence = (round(triangle_base * (1 - _STRUCTURE_RECURSIVE_WEIGHT)
                                 + triangle_recursive * _STRUCTURE_RECURSIVE_WEIGHT, 3)
                           if triangle_attempted else triangle_base)
    complex_correction_confidence = (round(combo_base * (1 - _STRUCTURE_RECURSIVE_WEIGHT)
                                           + combo_recursive * _STRUCTURE_RECURSIVE_WEIGHT, 3)
                                     if combo_attempted else combo_base)
    diagonal_confidence = (round(diagonal_base * (1 - _STRUCTURE_RECURSIVE_WEIGHT)
                                 + diagonal_recursive * _STRUCTURE_RECURSIVE_WEIGHT, 3)
                           if diagonal_attempted else diagonal_base)

    lo = max(0, at_index - window + 1)
    seg = swings[lo:at_index + 1]
    if len(seg) < MIN_WINDOW_SWINGS:
        scores = {t: 0.0 for t in StructureType if t not in (StructureType.TRENDING_IMPULSE, StructureType.CORRECTIVE)}
        scores[StructureType.POTENTIAL_TRIANGLE] = triangle_confidence
        scores[StructureType.POTENTIAL_COMPLEX_CORRECTION] = complex_correction_confidence
        scores[StructureType.POTENTIAL_DIAGONAL] = diagonal_confidence
        winner = max(scores, key=scores.get)
        winner_confidence = scores[winner]
        if winner_confidence < MIN_WINNER_CONFIDENCE:
            winner = StructureType.UNKNOWN
        detail, sub_type = _route_detail(winner, triangle, combo, diagonal)
        return StructureConfidence(scores=scores, winner=winner, winner_confidence=winner_confidence,
                                   winner_detail=detail, sub_type=sub_type)

    labels = _label_sequence(seg)

    # ---- existing signals (progression / persistence / momentum / direction) ----
    total_move = abs(seg[-1].price - seg[0].price)
    total_churn = sum(abs(seg[i].price - seg[i - 1].price) for i in range(1, len(seg)))
    net_progress = (total_move / total_churn) if total_churn > 0 else 0.0

    reversals = 0
    last_high_label = last_low_label = None
    for s, lab in zip(seg, labels):
        if lab is None:
            continue
        if s.kind == SwingType.HIGH:
            if last_high_label is not None and lab != last_high_label:
                reversals += 1
            last_high_label = lab
        else:
            if last_low_label is not None and lab != last_low_label:
                reversals += 1
            last_low_label = lab
    persistence_score = max(0.0, 1.0 - reversals / 3.0)

    leg_amplitudes = [abs(seg[i].price - seg[i - 1].price) for i in range(1, len(seg))]
    last_leg = leg_amplitudes[-1] if leg_amplitudes else 0.0
    rest = leg_amplitudes[:-1]
    prior_avg = (sum(rest) / len(rest)) if rest else last_leg
    amplitude_ratio = (last_leg / prior_avg) if prior_avg > 0 else 1.0
    momentum_score = min(amplitude_ratio, 1.5) / 1.5

    want_high_label = StructureLabel.HH if direction == "up" else StructureLabel.LH
    want_low_label = StructureLabel.HL if direction == "up" else StructureLabel.LL
    high_labels = [lab for s, lab in zip(seg, labels) if s.kind == SwingType.HIGH and lab is not None]
    low_labels = [lab for s, lab in zip(seg, labels) if s.kind == SwingType.LOW and lab is not None]
    direction_confirmed = (
        (not high_labels or high_labels[-1] == want_high_label)
        and (not low_labels or low_labels[-1] == want_low_label)
    )
    direction_score = 1.0 if direction_confirmed else 0.0

    # ---- subdivision evidence (SECONDARY -- see "PROVISIONAL STATUS --
    # MIGRATED" in module docstring) ----
    five_wave, three_wave = _subdivision_evidence(seg)
    subdivision_available = len(leg_amplitudes) >= 2   # need >=2 legs to say anything at all

    # ---- recursive structural verification (PRIMARY when available) ----
    # Only attempted when a caller has opted in via set_recursion_context
    # (currently wave_analysis.py; NOT wave_numbering.py, unmodified per
    # explicit requirement) AND the window's own bar range is wide enough to
    # be worth re-detecting at a finer degree. Task 3 Improvement: ONE call
    # to the unified detector (not two separate impulse/correction calls --
    # requirement 3, remove duplicate decision logic) -- whichever pattern
    # it resolves to informs that ONE matching hypothesis; the window
    # simply isn't read as impulse-shaped when it resolves to something
    # else, exactly as a genuine miss would.
    recursive_df = _recursion_df_var.get()
    bar_start, bar_end = seg[0].index, seg[-1].index
    recursion_available = (
        recursive_df is not None
        and bar_end - bar_start >= _RECURSION_MIN_SWINGS
    )
    recursive_impulse_conf = 0.0
    recursive_correction_conf = 0.0
    if recursion_available:
        rv = verify_recursive_structure(
            recursive_df, bar_start, bar_end, _unified_recursive_detector, "unified",
            max_depth=_RECURSION_MAX_DEPTH, min_swings=_RECURSION_MIN_SWINGS,
            min_confidence=_RECURSION_MIN_CONFIDENCE,
        )
        if rv.verified:
            if rv.resolved_type == "impulse":
                recursive_impulse_conf = rv.confidence
            elif rv.resolved_type in _SIMPLE_CORRECTION_LABELS:
                recursive_correction_conf = rv.confidence

    # ---- POTENTIAL_IMPULSE confidence: weighted average, re-normalized
    # whenever a component isn't available. Task 3 Improvement (requirement
    # 3, "remove remaining heuristic subdivision decisions wherever
    # possible"): the leg-SIZE heuristic (_subdivision_evidence) is now
    # ONLY consulted when genuine recursive verification is unavailable at
    # all (no DataFrame context) -- previously it stayed in the blend at a
    # reduced ~10% weight even alongside real recursion; now that recursion
    # covers all five hypothesis types (not just impulse-or-correction), it
    # has nothing left to add whenever recursion actually ran, so it's
    # dropped from the blend entirely in that case rather than kept as a
    # token weight. Still computed and exposed (five_wave_evidence/
    # three_wave_evidence fields) for backward compatibility -- see module
    # docstring's "PROVISIONAL STATUS" section. ----
    if recursion_available:
        impulse_components = [
            (net_progress, 0.15), (persistence_score, 0.10),
            (momentum_score, 0.10), (direction_score, 0.10),
            (recursive_impulse_conf, _RECURSIVE_WEIGHT),
        ]
    else:
        impulse_components = [
            (net_progress, 0.25), (persistence_score, 0.20),
            (momentum_score, 0.15), (direction_score, 0.15),
        ]
        if subdivision_available:
            impulse_components.append((five_wave, _SUBDIVISION_WEIGHT_NO_RECURSION["impulse"]))
    impulse_confidence = round(
        sum(v * w for v, w in impulse_components) / sum(w for _, w in impulse_components), 3)

    # ---- POTENTIAL_CORRECTION confidence: same treatment -- subdivision
    # heuristic only when recursion isn't available at all. ----
    if recursion_available:
        correction_components = [
            (min(net_progress / NET_PROGRESS_TRENDING, 1.0), 0.10),
            (1.0 - direction_score, 0.15),
            (recursive_correction_conf, _RECURSIVE_WEIGHT),
        ]
    else:
        correction_components = [
            (min(net_progress / NET_PROGRESS_TRENDING, 1.0), 0.20),
            (1.0 - direction_score, 0.25),
        ]
        if subdivision_available:
            correction_components.append((three_wave, _SUBDIVISION_WEIGHT_NO_RECURSION["correction"]))
    weight_sum = sum(w for _, w in correction_components)
    correction_confidence = round(
        sum(v * w for v, w in correction_components) / weight_sum, 3) if weight_sum else 0.0

    # ---- SIDEWAYS confidence: low net progress, unstable structure. ----
    sideways_confidence = round(
        max(0.0, 1.0 - net_progress / NET_PROGRESS_TRENDING) * 0.6
        + max(0.0, (reversals - 1) / 3.0) * 0.4, 3)

    scores: Dict[StructureType, float] = {
        StructureType.POTENTIAL_IMPULSE: impulse_confidence,
        StructureType.POTENTIAL_CORRECTION: correction_confidence,
        StructureType.SIDEWAYS: sideways_confidence,
        StructureType.UNKNOWN: 0.0,
        # Task 7 (v4) -- real scores computed above (0.0 when no candidate
        # was passed in, e.g. any pre-Task-7 caller) instead of the old
        # unconditional _UNSUPPORTED loop.
        StructureType.POTENTIAL_TRIANGLE: triangle_confidence,
        StructureType.POTENTIAL_COMPLEX_CORRECTION: complex_correction_confidence,
        StructureType.POTENTIAL_DIAGONAL: diagonal_confidence,
    }

    winner = max(scores, key=scores.get)
    winner_confidence = scores[winner]
    if winner_confidence < MIN_WINNER_CONFIDENCE:
        winner = StructureType.SIDEWAYS
    detail, sub_type = _route_detail(winner, triangle, combo, diagonal)

    return StructureConfidence(
        scores=scores, winner=winner, winner_confidence=winner_confidence,
        five_wave_evidence=five_wave, three_wave_evidence=three_wave,
        winner_detail=detail, sub_type=sub_type,
    )


def classify_structure(swings: List[Swing], at_index: int, direction: str,
                       window: int = DEFAULT_WINDOW,
                       triangle: Optional["CorrectiveCandidate"] = None,
                       combo: Optional["CorrectiveCandidate"] = None,
                       diagonal: Optional["DiagonalCandidate"] = None) -> StructureType:
    """Backward-compatible wrapper -- SAME name and return type as before
    Task 7 (original callers passing only ``swings, at_index, direction[,
    window]`` positionally are entirely unaffected -- the three new
    parameters are trailing and keyword-defaulted). Returns just the
    highest-confidence hypothesis; use ``classify_structure_detailed`` for
    the full per-hypothesis confidence breakdown AND ``winner_detail``
    (needed by ``wave_numbering._generate_candidates`` to avoid re-running
    detection -- this thin wrapper discards it, so it's for callers that
    only need the label).
    """
    return classify_structure_detailed(swings, at_index, direction, window,
                                       triangle, combo, diagonal).winner


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    def _mk(idx: int, price: float, kind: SwingType) -> Swing:
        return Swing(idx, idx + 2, price, kind)

    H, L = SwingType.HIGH, SwingType.LOW

    def _show(name: str, swings: List[Swing], direction: str) -> None:
        c = classify_structure_detailed(swings, len(swings) - 1, direction)
        print(f"=== {name} ===")
        print(f"  winner: {c.winner.value}  (confidence {c.winner_confidence:.2f})")
        print(f"  five_wave_evidence={c.five_wave_evidence:.2f}  three_wave_evidence={c.three_wave_evidence:.2f}")
        print("  all scores:", {k.value: v for k, v in c.scores.items() if v > 0 or k == c.winner})
        print()

    _show("a genuine 5-leg motive run (big-small-big-small-big, persistent HH/HL)",
         [_mk(0, 100, L), _mk(2, 110, H), _mk(4, 106, L), _mk(6, 130, H),
          _mk(8, 126, L), _mk(10, 150, H)], "up")

    _show("a sharp, EFFICIENT zigzag correction (high net progress, only 3 legs -- "
         "the exact case v1's momentum-only classifier would have misread as impulse)",
         [_mk(0, 100, L), _mk(2, 130, H), _mk(4, 108, L), _mk(6, 112, H)], "up")

    _show("a sideways range (alternating, no net progress)",
         [_mk(0, 100, L), _mk(2, 110, H), _mk(4, 101, L), _mk(6, 109, H),
          _mk(8, 100, L), _mk(10, 110, H)], "up")

    _show("a lone leg with no prior context (chart-opening case)",
         [_mk(0, 100, L), _mk(2, 110, H)], "up")

    _show("genuinely too few swings to judge (a single pivot)",
         [_mk(0, 100, L)], "up")
