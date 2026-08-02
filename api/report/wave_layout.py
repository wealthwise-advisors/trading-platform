"""
wave_layout.py
==============

Static-report port of web/src/lib/waveLabelLayout.ts's collision logic,
plus web/src/components/charts/ElliottWaveChart.tsx's structural
segmentation (splitIntoSegments/labelSegments). The exported HTML report
is a fixed snapshot -- there's no React onRelayout to re-run decluttering
as the user zooms, but the same non-destructive design applies: nothing is
ever hidden.

Keep in sync with waveLabelLayout.ts / ElliottWaveChart.tsx if either
changes -- this is a deliberate, documented duplication (a static image
has no shared runtime with the React app to import from), not drift.

Bugs fixed here 2026-07-19, alongside the equivalent React-side fixes:

  1. This module used to HIDE labels two ways -- `tier_filter_run` capped
     the connecting line/marker trace to a fixed subset (unconditionally,
     since a static image has no zoom to reveal more), and
     `declutter_static` kept only the highest-priority label at any
     crowded spot and dropped the rest outright. Any fixed collision
     threshold eventually collides on a busy enough chart, and deleting
     the loser is silent hiding of exactly the numbers a trader needs to
     see. Fixed the same way as the live chart: collisions now fan the
     losing label outward (`stack_index`) instead of deleting it; the
     line/marker trace always draws every point.
  2. `tier_of` lumped triangle/combination letters into the same bucket as
     internal continuation numbers -- kept as the collision-priority
     tiebreak (odd position vs. even position within a segment), same role
     waveLabelLayout.ts's tierOf still plays.

Bug fixed here 2026-07-20, alongside the equivalent React-side fix: this
module used to split a run into a new segment only at a fresh "1" or a
numeric/letter kind change -- so several genuinely distinct, independently-
detected corrective structures running back-to-back with no numeric point
between them (e.g. an ABC correction immediately followed by three separate
Double Threes) all merged into ONE segment/box labeled generically
"Wave N", even though the engine had detected four separate structures.
Fixed by also splitting on "a" and "w" (the first label of every
correction/triangle/combination type), and by labeling each corrective
segment with its actual detected type (ABC Correction/Triangle/WXY
Correction/Triple Three) instead of a generic ordinal -- see
`_FRESH_STRUCTURE_TOKENS` and `describe_structure_type` below.

Bug fixed here 2026-07-27, alongside the equivalent React-side fix
(reversing the 2026-07-18/07-21 "plain digit only" requirement, per
explicit new feedback that this doesn't match real Elliott Wave notation):
`to_simple_items` used to renumber EVERY point's label to a plain digit
("1".."N"), regardless of whether the engine's real label was a number or
a letter -- so a corrective structure (always lettered -- A-B-C, A-B-C-D-E,
W-X-Y, W-X-Y-X-Z in real Elliott notation) displayed as a digit-filled
"Correction #N (1-M)" box instead. Renamed to `split_into_segments`: it now
returns each segment's items UNCHANGED (no renumbering) -- `display_wave()`
below is the only text transform applied for display, and it just
uppercases corrective letters, leaving digits alone. `label_segments`
correspondingly builds each corrective segment's header from its own real
letter span (e.g. "ABC Correction (A–C)") instead of a fake numeric range.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, TypedDict

# Kept only as the collision-priority tiebreak now (see module docstring,
# bug 2) -- every displayed label is a plain digit post-relabeling, so
# these buckets just distinguish odd/even position within a segment, not
# a visual-weight or visibility gate (waveLabelLayout.ts's LABEL_STYLE
# equivalent, _EW_TIER_STYLE in report.py, is uniform across all of them).
CORE_WAVES = {"1", "3", "5"}
SECONDARY_WAVES = {"2", "4"}


def tier_of(wave: str) -> int:
    if wave in CORE_WAVES:
        return 0
    if wave in SECONDARY_WAVES:
        return 1
    return 2


def priority_of(wave: str, sub: Optional[int]) -> float:
    tier = tier_of(wave)
    tier_score = (2 - tier) * 10
    sub_score = 2 if sub == 1 else (0.5 if sub == 2 else 1)
    return tier_score + sub_score


class WaveItem(TypedDict):
    t: float        # epoch seconds
    price: float
    wave: str
    sub: Optional[int]
    kind: str        # "high" | "low"


# --------------------------------------------------------------------------- #
# Structural segmentation -- see web/src/components/charts/ElliottWaveChart.tsx's
# splitIntoSegments for the full rationale (identical rule here, Python
# port). A new segment begins whenever: the engine's own label is "a" or
# "w" -- the first label of a corrective structure (simple correction/
# triangle start "a", double/triple three start "w" -- see
# wave_numbering.py's _select_best_counts, complex_corrections.py,
# diagonal_waves.py); or the label's KIND changes from the previous point's
# (numeric digits vs. letters -- an impulse's "5" into its closing
# correction's "a" is the impulse ending and a new corrective structure
# beginning). An impulse/diagonal's own "1" only ever appears as the first
# element of a `_group_wave_runs` run (report.py), so it doesn't need to be
# listed here as a mid-run boundary. Every point keeps its REAL label --
# `display_wave()` below is the only text transform applied, for display
# only.
# --------------------------------------------------------------------------- #
_NUMERIC_RE = re.compile(r"^\d+$")
_LETTER_RE = re.compile(r"^[a-z]$")

# The first label of a corrective structure -- see the comment block above.
_FRESH_STRUCTURE_TOKENS = {"a", "w"}

# Verbatim label sequences wave_numbering.py/complex_corrections.py ever
# produce for a corrective structure -- see describe_structure_type().
_STRUCTURE_TYPE_NAMES = {
    "a,b,c": "ABC Correction",
    "a,b,c,d,e": "Triangle",
    "w,x,y": "WXY Correction",
    "w,x,y,x,z": "Triple Three",
}


def display_wave(wave: str) -> str:
    """The only text transform applied to a real engine label for display:
    corrective letters ("a".."z") uppercase to match standard Elliott
    notation; numeric labels ("1".."11") pass through unchanged."""
    return wave.upper() if _LETTER_RE.match(wave) else wave


def split_into_segments(run: List[WaveItem]) -> List[List[WaveItem]]:
    """Splits ONE run into segments at every genuine structural boundary --
    see the module-level comment above. Returns each segment's items
    UNCHANGED (no renumbering, no relabeling) -- callers that want the
    on-screen text use `display_wave()` per item."""
    segments: List[List[WaveItem]] = []
    prev_kind: Optional[str] = None

    for it in run:
        kind = "numeric" if _NUMERIC_RE.match(it["wave"]) else "letter"
        is_fresh_structure_start = it["wave"] in _FRESH_STRUCTURE_TOKENS
        kind_changed = prev_kind is not None and kind != prev_kind

        if is_fresh_structure_start or kind_changed or not segments:
            segments.append([])
        segments[-1].append(it)
        prev_kind = kind

    return segments


def describe_structure_type(segment: List[dict]) -> Optional[str]:
    """Human-readable structure-type name from a segment's REAL label
    sequence -- segment[i]["wave"], never renumbered now. Python port of
    ElliottWaveChart.tsx's describeStructureType(), same four exact label
    sequences, same None fallback (numeric impulse/diagonal segments, or
    anything that doesn't match one of the four corrective shapes) so
    callers keep the plain "Wave N" header for those. Keep in sync if
    either changes."""
    seq = ",".join(it["wave"] for it in segment)
    return _STRUCTURE_TYPE_NAMES.get(seq)


class SegmentLabel(TypedDict):
    display: str              # what's shown on screen, e.g. "ABC Correction (A–C)"
    technical: Optional[str]  # real Elliott type name, also used in the hover text


def label_segments(segments: List[List[dict]], zero_indexed: bool) -> List[SegmentLabel]:
    """One label per segment -- Python port of ElliottWaveChart.tsx's
    labelSegments(). Numeric (impulse/diagonal) segments count
    independently as "Wave N (1-{len})", unchanged. Corrective segments are
    named by their real technical type plus their own letter span, e.g.
    "ABC Correction (A–C)" / "Triangle (A–E)" / "WXY Correction (W–Y)" /
    "Triple Three (W–Z)" -- real Elliott notation, matching
    elliottwave-forecast.com's own diagrams (reversing the earlier
    2026-07-21 "plain Correction, no jargon" simplification). A per-type
    ordinal "#N" suffix only appears when that SAME technical type recurs
    in this structure-set. Keep in sync with the TS version if either
    changes."""
    structure_types = [describe_structure_type(seg) for seg in segments]
    total_by_type: dict[str, int] = {}
    for t in structure_types:
        if t:
            total_by_type[t] = total_by_type.get(t, 0) + 1
    seen_by_type: dict[str, int] = {}
    wave_seen = 0 if zero_indexed else 1

    out: List[SegmentLabel] = []
    for seg, technical in zip(segments, structure_types):
        if technical:
            seen_by_type[technical] = seen_by_type.get(technical, 0) + 1
            suffix = f" #{seen_by_type[technical]}" if total_by_type[technical] > 1 else ""
            span = f"{display_wave(seg[0]['wave'])}–{display_wave(seg[-1]['wave'])}"
            out.append({"display": f"{technical}{suffix} ({span})", "technical": technical})
        else:
            out.append({"display": f"Wave {wave_seen} (1-{len(seg)})", "technical": None})
            wave_seen += 1
    return out


MIN_SPACING_T_FRACTION = 0.022
MIN_SPACING_P_FRACTION = 0.045


def declutter_static(
    items: List[WaveItem],
    t_span: float,
    p_span: float,
    allowed_tiers: Iterable[int] = None,
) -> List[dict]:
    """Same-lane (high/low), genuine 2D (time AND price) collision pass --
    never hides a candidate; a colliding one fans outward (`stack_index`)
    instead. `allowed_tiers` is accepted for backward-compatible call
    signatures but no longer filters anything (see module docstring, bug 1).
    Returns dicts of {**item, "stack_index": int} rather than bare
    WaveItems, since stack_index is new caller-facing information.
    """
    t_span = t_span or 1.0
    p_span = p_span or 1e-9
    by_priority = sorted(items, key=lambda it: (-priority_of(it["wave"], it["sub"]), it["t"]))

    lanes: dict[str, List[dict]] = {"high": [], "low": []}
    shown: List[dict] = []
    for cand in by_priority:
        lane = lanes[cand["kind"]]
        colliders = [
            p for p in lane
            if abs(p["t"] - cand["t"]) / t_span < MIN_SPACING_T_FRACTION
            and abs(p["price"] - cand["price"]) / p_span < MIN_SPACING_P_FRACTION
        ]
        stack_index = 0 if not colliders else max(p["stack_index"] for p in colliders) + 1
        placed = {**cand, "stack_index": stack_index}
        lane.append(placed)
        shown.append(placed)
    shown.sort(key=lambda it: it["t"])
    return shown


def tier_filter_run(run: List[WaveItem], allowed_tiers: Iterable[int] = None) -> List[WaveItem]:
    """Full detail, every point, always -- kept as a named passthrough
    (rather than inlining `run` at call sites) so report.py reads as "the
    line is deliberately full-detail," not as if filtering was forgotten.
    `allowed_tiers` is accepted for backward-compatible call signatures
    but no longer filters anything (see module docstring, bug 1)."""
    return run
