"""
wave_analysis.py
================

Capstone: an INTEGRATED, in-depth Elliott wave analyzer that orchestrates every
other module into one read of the market.

Pipeline per call
------------------
  swing_identification  -> confirmed pivots + structure (HH/HL/LH/LL, trend)
  wave_numbering         -> continuous chart-wide wave count (Wave 1, 2.1, 3.1...)
  elliott_wave          -> validated impulse (hard rules), single best window
  corrective_waves      -> the following correction's type (zigzag/flat/combo)
  fibonacci             -> proportion quality + projected confluence zones
  -> a WaveAnalysis: cycle position, bias, invalidation, target zones, ALTERNATES

Depth features
--------------
* Multi-degree (fractal) analysis: run detection recursively down a ladder of
  sensitivities (Primary -> Intermediate -> Minor -> Minute -> ...), each level
  confined to its parent's own wave legs -- see DEFAULT_DEGREE_LADDER.
* Alternate counts: Elliott is probabilistic; we surface competing reads and the
  price that invalidates the primary one, rather than pretending to one answer.

Honesty: every output is a CANDIDATE read to be confirmed or invalidated by
subsequent price. Structure + Fibonacci raise the odds; they do not remove risk.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import List, Optional

import numpy as np
import pandas as pd

from .swing_identification import (
    Swing, SwingType, identify_swings, trend_state, atr,
)
from .indicators import calc_rsi
from .elliott_wave import ImpulseWave, find_impulses
from .corrective_waves import (
    Correction, CorrectionType, classify_abc, detect_triangle, find_combinations,
)
from .fibonacci import (
    score_impulse_fib, score_correction_fib, correction_end_zone,
    project_correction_c, fib_projections, find_confluence, ClusterZone,
)
from .wave_numbering import WaveLabel, label_wave_sequence
from . import structure_classification


@dataclass
class WaveAnalysis:
    degree: str
    trend: str
    n_swings: int
    impulse: Optional[ImpulseWave]
    impulse_fib: Optional[dict]
    correction: Optional[Correction]
    correction_fib: Optional[dict]
    cycle_position: str
    bias: str
    invalidation: Optional[float]
    target_zones: List[ClusterZone] = field(default_factory=list)
    alternates: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    # Distinct from ``notes`` (general interpretive commentary): each entry
    # here explains a SPECIFIC count that stopped short of completion because
    # of a rule the numbering couldn't confirm (currently: Wave 5 momentum
    # divergence -- see wave_numbering.label_wave_sequence's ``warnings``
    # return). Kept separate so the UI can style these as actionable
    # warnings rather than mixing them into general notes.
    warnings: List[str] = field(default_factory=list)
    wave_sequence: List[WaveLabel] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Locate the correction that follows an impulse
# --------------------------------------------------------------------------- #
def _find_correction(swings: List[Swing], impulse: ImpulseWave) -> Optional[Correction]:
    """The correction that begins at the impulse's terminal pivot (P5)."""
    last = impulse.pivots[-1]
    pos = next((k for k, s in enumerate(swings)
                if s.index == last.index and s.kind == last.kind), None)
    if pos is None:
        return None

    # prefer a complex combination that starts exactly here
    for combo in find_combinations(swings):
        if combo.pivots[0].index == last.index:
            return combo

    # else a simple ABC from the next 4 pivots (S=P5, A, B, C)
    if pos + 4 <= len(swings):
        return classify_abc(swings[pos:pos + 4])
    return None


# --------------------------------------------------------------------------- #
# Interpretation: cycle position / bias / invalidation / alternates
# --------------------------------------------------------------------------- #
def _interpret(impulse, correction, price, trend):
    notes, alternates = [], []

    if impulse is None:
        bias = {"uptrend": "long", "downtrend": "short"}.get(trend, "neutral")
        return (f"no validated impulse at this degree; structure = {trend}",
                bias, None, alternates, notes)

    P = [p.price for p in impulse.pivots]
    origin, top = P[0], P[5]
    dirn = impulse.direction
    invalidation = origin  # breaching wave-1 origin voids the count

    if correction is None:
        pos = f"{dirn}-impulse complete (W1-W5); no correction detected yet"
        bias = "neutral"
        notes.append("impulse done -> expect a correction before resumption; stand aside or fade with care")
        alternates.append("wave 5 may still be extending; a new high/low would push the W5 label out")
    else:
        ctype = correction.type.value
        pos = f"{dirn}-impulse complete; corrective '{ctype}' in progress"
        # after a correction we expect the impulse direction to resume
        bias = "long" if dirn == "up" else "short"
        notes.append(f"trade the resumption {bias.upper()} as the correction completes near a support/target zone")
        if correction.type == CorrectionType.ZIGZAG:
            alternates.append("sharp zigzag -> strong resumption likely; but it may be wave A of a larger flat")
        elif "flat" in ctype:
            alternates.append("flat/expanded -> sideways; could morph into a triangle or a double three")
        else:
            alternates.append("complex correction -> more sideways time possible before resumption")
        alternates.append(f"if price breaches origin {origin:.2f}, the impulse count is invalidated")

    return pos, bias, invalidation, alternates, notes


# --------------------------------------------------------------------------- #
# Single-degree analysis
# --------------------------------------------------------------------------- #
def analyze(df: pd.DataFrame, left: int = 2, right: int = 2,
            min_move: float = 0.0, degree: str = "minor") -> WaveAnalysis:
    swings = identify_swings(df, left=left, right=right, min_move=min_move)
    trend = trend_state(swings)
    # RSI(14): textbook Elliott Wave momentum-divergence gate for Wave 5 (see
    # wave_numbering.py docstring). Deliberately NOT bfilled -- per explicit
    # requirement, Wave 5 must not complete when momentum can't genuinely be
    # evaluated, and bfilling the warm-up NaNs would borrow a future value
    # and mask exactly that "insufficient data" case label_wave_sequence is
    # now designed to detect and warn about.
    rsi14 = calc_rsi(df["close"], 14)
    # Opt in to recursive structural verification (Task 4) for this call
    # only -- swings.index values here are bar offsets in `df` itself, so
    # this is the one place in the pipeline where the coordinate spaces
    # genuinely line up. Tightly scoped (set immediately before, reset
    # immediately after) so the nested child-degree hierarchy pass
    # (_nested_wave_sequence, which calls label_wave_sequence again
    # but on a DIFFERENT, slice-local `df`) never sees this context and
    # never risks a coordinate mismatch. wave_numbering.py itself is
    # unmodified and never calls set_recursion_context.
    _recursion_token = structure_classification.set_recursion_context(df)
    try:
        wave_sequence, wave_warnings, wave_alternates = label_wave_sequence(swings, rsi=rsi14)
    finally:
        structure_classification.reset_recursion_context(_recursion_token)

    valid = [w for w in find_impulses(swings) if w.valid]
    impulse = max(valid, key=lambda w: w.end_index) if valid else None
    impulse_fib = score_impulse_fib(impulse) if impulse else None

    correction = _find_correction(swings, impulse) if impulse else None
    correction_fib = (score_correction_fib(correction)
                      if correction and correction.type in
                      (CorrectionType.ZIGZAG, CorrectionType.REGULAR_FLAT,
                       CorrectionType.EXPANDED_FLAT, CorrectionType.RUNNING_FLAT)
                      else None)

    price = float(df["close"].iloc[-1])
    cycle, bias, invalidation, alternates, notes = _interpret(
        impulse, correction, price, trend)
    # wave_alternates: competitive-but-not-chosen counts from the scored
    # selection over the continuous wave_sequence (see wave_numbering.py's
    # _select_best_counts) -- a different axis from _interpret()'s single-
    # window alternates above, both surfaced the same way to the UI.
    alternates = alternates + wave_alternates

    # ---- confluence target zones (mingle impulse + corrective levels) ----
    zones: List[ClusterZone] = []
    if impulse:
        P = [p.price for p in impulse.pivots]
        origin, top = P[0], P[5]
        levels = []
        for r, px in correction_end_zone(origin, top).items():
            levels.append((px, f"impulse-retr {int(r*100)}%"))
        if correction and len(correction.pivots) >= 3:
            S, A, B = (p.price for p in correction.pivots[:3])
            for r, px in project_correction_c(S, A, B).items():
                levels.append((px, f"C x{r}"))
        # resumption targets: project the impulse length beyond its top
        for r, px in fib_projections(top, origin, top, ratios=[0.618, 1.0, 1.618]).items():
            levels.append((px, f"cont x{r}"))
        zones = find_confluence(levels, tol_frac=0.01)

        # surface nearest support / target relative to current price
        below = [z for z in zones if z.center < price]
        above = [z for z in zones if z.center > price]
        if below:
            nz = max(below, key=lambda z: z.center)
            notes.append(f"nearest support confluence ~{nz.center} (strength {nz.strength})")
        if above:
            nz = min(above, key=lambda z: z.center)
            notes.append(f"nearest target confluence ~{nz.center} (strength {nz.strength})")

    return WaveAnalysis(
        degree=degree, trend=trend, n_swings=len(swings),
        impulse=impulse, impulse_fib=impulse_fib,
        correction=correction, correction_fib=correction_fib,
        cycle_position=cycle, bias=bias, invalidation=invalidation,
        target_zones=zones, alternates=alternates, notes=notes,
        warnings=wave_warnings,
        wave_sequence=wave_sequence,
    )


# --------------------------------------------------------------------------- #
# Degree hierarchy (2026-07-19): Minor must nest inside Primary
# --------------------------------------------------------------------------- #
# Previously "primary" and "minor" were two independent flat scans of the
# WHOLE chart at different pivot sensitivities, with zero relationship
# between them -- a Minor wave count could span, start, or end anywhere,
# regardless of what Primary found covering the same bars. That's not
# Elliott degree structure, it's just two unrelated readings of the same
# price series. Real Elliott theory is fractal: a Primary impulse leg (Wave
# 1, 3, 5...) is ITSELF composed of exactly 5 Minor sub-waves; a Primary
# corrective leg (Wave 2, 4, A, B, C) is composed of a Minor A-B-C. The
# child never exists outside the parent's own price/time boundaries.
#
# Enforcement below is structural, not a filter bolted on after the fact:
#   1. Containment -- Minor's swings and candidates are generated ONLY from
#      the bars inside [leg_start, leg_end] (a literal df slice). There is
#      no code path by which a nested Minor label's bar index can fall
#      outside its parent leg -- it's not filtered afterward, it never
#      existed outside that range to begin with.
#   2. Elliott-consistent subdivision -- each Primary leg's ROLE (impulse:
#      1/3/5/odd-continuation, expects 5 Minor waves; corrective:
#      2/4/even-continuation/a/b/c, expects a Minor A-B-C) is compared
#      against what the nested scan actually found and reported either way
#      (not forced -- manufacturing a fake 5th wave when only 3 genuine
#      sub-pivots exist would be false precision, not accuracy).
#   3. No conflicting counts -- among the Minor sub-runs found inside a
#      leg's slice, only ones whose overall direction matches the parent
#      leg are kept; a Minor reading that disagrees with its own parent's
#      direction is dropped, never surfaced as if it were a real nesting.
#   4. Post-hoc validation -- every leg produces a ``_LegHierarchyCheck``
#      regardless of whether a usable subdivision was found, so the result
#      is auditable, not just "whatever happened to come out."
#
# Corrective sub-typing (2026-07-19): a corrective Primary leg's Minor
# subdivision is now classified by corrective_waves.py's own machinery
# (zigzag/flat variants, triangle, double/triple three) instead of assuming
# every correction is a plain zigzag-shaped A-B-C. Tried in order of
# structural specificity -- combination > triangle > simple ABC, since a
# leg that genuinely fits a WXY is a more specific, stronger claim than "it
# happened to also pass as *some* ABC" -- with a direction check identical
# in spirit to impulse legs' (requirement 3 applies here too: a
# classification whose net direction disagrees with the parent leg is
# rejected). IMPULSE legs are completely untouched by this -- they still go
# through wave_numbering.label_wave_sequence exactly as before, and if a
# corrective leg's shape doesn't cleanly match any corrective_waves.py
# pattern, it falls back to the same label_wave_sequence-based ABC reading
# used previously, so nothing regresses; this only ADDS a preferred, more
# specific reading when one is available.
# --------------------------------------------------------------------------- #

def _leg_role(wave: str) -> str:
    """Impulse legs (1, 3, 5, and odd continuation waves 7/9/11) are motive
    -- Elliott's rule says they subdivide into 5. Corrective legs (2, 4,
    even continuation waves 6/8/10, and a/b/c) subdivide into 3 (A-B-C)."""
    if wave.isdigit():
        return "impulse" if int(wave) % 2 == 1 else "corrective"
    return "corrective"   # a, b, c


def _group_wave_runs(sequence: List[WaveLabel]) -> List[List[WaveLabel]]:
    """Same grouping rule used by the API/frontend/report: a new run starts
    every time the count resets back to Wave 1."""
    runs: List[List[WaveLabel]] = []
    for w in sequence:
        if w.wave == "1" or not runs:
            runs.append([w])
        else:
            runs[-1].append(w)
    return runs


def _origin_before(label: WaveLabel, swings: List[Swing]) -> Optional[Swing]:
    """The swing immediately preceding ``label`` in the full swing series --
    mirrors what wave_numbering._grow_count uses internally as a run's
    origin (swings[start-1]), recovered here since the flat WaveLabel
    sequence doesn't carry the origin explicitly."""
    earlier = [s for s in swings if s.index < label.swing.index]
    return max(earlier, key=lambda s: s.index) if earlier else None


@dataclass
class _LegHierarchyCheck:
    parent_wave: str
    role: str
    bar_start: int
    bar_end: int
    minor_found: bool
    matches_theory: bool
    note: str


def _classify_corrective_leg(slice_swings: List[Swing], expected_dir: str) -> Optional[Correction]:
    """Best-effort shape classification for a corrective Primary leg's own
    swings, tried most-specific-first: combination (double/triple three) >
    triangle > simple zigzag/flat variants. Returns None if nothing fits or
    the only fit disagrees in direction with the parent leg (see module
    section docstring, "Corrective sub-typing").

    Each corrective_waves.py function answers a different question:
    ``find_combinations`` SCANS the whole list for an 8- or 12-pivot WXY/
    WXYXZ window anywhere inside it, so results are filtered here to ones
    starting at this leg's own first pivot -- a combination found only
    somewhere in the MIDDLE of the leg doesn't describe the leg itself.
    ``detect_triangle``/``classify_abc`` take an explicit pivot list and
    don't scan, so they're handed exactly the leg's first 6 / first 4
    pivots -- "does this leg, from its own start, look like a triangle /
    simple ABC."
    """
    combos = [c for c in find_combinations(slice_swings)
             if c.pivots[0] is slice_swings[0] and c.direction == expected_dir]
    if combos:
        return max(combos, key=lambda c: len(c.pivots))   # prefer triple three over double three if both fit

    if len(slice_swings) >= 6:
        tri = detect_triangle(slice_swings[:6])
        if tri and tri.direction == expected_dir:
            return tri

    if len(slice_swings) >= 4:
        abc = classify_abc(slice_swings[:4])
        if abc.direction == expected_dir:
            return abc

    return None


def _correction_boundary_labels(correction: Correction, direction: str) -> List[WaveLabel]:
    """Map a classified Correction onto WaveLabels at its TOP level: a
    zigzag/flat's own A/B/C, a triangle's A..E, or a combination's W/X/Y
    connector boundaries. Sub-corrections inside a combination (W's and
    Y's/Z's own internal A-B-C) are NOT recursively re-labeled in this pass
    -- documented as a follow-on in the module docstring, not silently
    dropped.
    """
    p = correction.pivots
    if correction.type == CorrectionType.TRIANGLE:
        boundary = list(zip(["a", "b", "c", "d", "e"], p[1:6]))
    elif correction.type == CorrectionType.DOUBLE_THREE:
        boundary = [("w", p[3]), ("x", p[4]), ("y", p[7])]
    elif correction.type == CorrectionType.TRIPLE_THREE:
        boundary = [("w", p[3]), ("x", p[4]), ("y", p[7]), ("x", p[8]), ("z", p[11])]
    else:   # zigzag / regular / expanded / running flat -- simple A, B, C
        boundary = list(zip(["a", "b", "c"], p[1:4]))
    return [WaveLabel(swing=swing, wave=label, sub=None, direction=direction)
            for label, swing in boundary]


def _nested_wave_sequence(
    df: pd.DataFrame,
    parent_sequence: List[WaveLabel],
    parent_swings: List[Swing],
    child_left: int, child_right: int, child_min_move: float,
    parent_degree_name: str = "primary", child_degree_name: str = "minor",
) -> tuple[List[WaveLabel], List[str], List[str], List[_LegHierarchyCheck]]:
    """Build a child-degree wave_sequence leg-by-leg WITHIN each of the
    parent degree's own selected waves, instead of independently over the
    whole chart. Generic over WHICH two adjacent degrees are being nested
    (Primary->Intermediate, Intermediate->Minor, Minor->Minute, ...) --
    ``analyze_degrees`` calls this once per adjacent pair down the degree
    ladder, feeding each level's own nested output back in as the next
    level's ``parent_sequence``/``parent_swings``, which is what makes the
    nesting genuinely recursive rather than hardcoded to exactly two
    levels. Returns (labels, warnings, alternates, checks) -- see module
    section docstring above for what each enforcement point means.
    """
    out: List[WaveLabel] = []
    warnings: List[str] = []
    alternates: List[str] = []
    checks: List[_LegHierarchyCheck] = []

    MIN_LEG_BARS = 4   # too short to meaningfully subdivide at all
    parent_label = parent_degree_name.capitalize()
    child_label = child_degree_name.capitalize()

    for run in _group_wave_runs(parent_sequence):
        origin = _origin_before(run[0], parent_swings)
        pivots = ([origin] if origin else []) + [w.swing for w in run]
        end_waves = (["1"] if origin else []) + [w.wave for w in run]

        for i in range(len(pivots) - 1):
            leg_start, leg_end = pivots[i], pivots[i + 1]
            end_wave = end_waves[i + 1]
            role = _leg_role(end_wave)
            bar_start, bar_end = leg_start.index, leg_end.index
            expected_dir = "up" if leg_end.price > leg_start.price else "down"

            if bar_end - bar_start < MIN_LEG_BARS:
                checks.append(_LegHierarchyCheck(
                    end_wave, role, bar_start, bar_end, minor_found=False, matches_theory=False,
                    note=f"{parent_label} Wave {end_wave} ({role}, bars {bar_start}-{bar_end}): "
                         f"too short to carry a {child_label} subdivision.",
                ))
                continue

            leg_label = f"{parent_label} Wave {end_wave} ({role}, bars {bar_start}-{bar_end})"
            slice_df = df.iloc[bar_start:bar_end + 1].reset_index(drop=True)
            slice_swings = identify_swings(slice_df, left=child_left, right=child_right,
                                           min_move=child_min_move)

            # Corrective legs: prefer corrective_waves.py's own shape
            # classification (zigzag/flat/triangle/combination) over the
            # generic impulse-numbering fallback below -- see "Corrective
            # sub-typing" in the module section docstring.
            if role == "corrective":
                shape = _classify_corrective_leg(slice_swings, expected_dir)
                if shape is not None:
                    offset_labels = [
                        WaveLabel(
                            swing=Swing(index=w.swing.index + bar_start,
                                       confirm_index=w.swing.confirm_index + bar_start,
                                       price=w.swing.price, kind=w.swing.kind, label=w.swing.label),
                            wave=w.wave, sub=w.sub, direction=w.direction,
                        )
                        for w in _correction_boundary_labels(shape, expected_dir)
                    ]
                    out.extend(offset_labels)
                    checks.append(_LegHierarchyCheck(
                        end_wave, role, bar_start, bar_end, minor_found=True, matches_theory=True,
                        note=f"{leg_label}: {child_label} subdivision recognized as a "
                             f"{shape.type.value.replace('_', ' ')}.",
                    ))
                    continue

            slice_rsi = calc_rsi(slice_df["close"], 14) if "close" in slice_df.columns else None
            sub_seq, sub_warnings, sub_alternates = label_wave_sequence(slice_swings, rsi=slice_rsi)
            sub_runs = _group_wave_runs(sub_seq)

            # Enforcement #3: only keep sub-runs whose OWN direction agrees
            # with the parent leg's direction -- a disagreeing reading is
            # dropped outright, not shown as a false nesting.
            consistent = [r for r in sub_runs if r[0].direction == expected_dir]
            chosen = max(consistent, key=lambda r: r[-1].index - r[0].index) if consistent else None

            if chosen is None:
                conflicted = len(sub_runs) > 0
                checks.append(_LegHierarchyCheck(
                    end_wave, role, bar_start, bar_end, minor_found=False, matches_theory=False,
                    note=f"{leg_label}: " + (
                        f"{child_label} subdivision(s) were found but all conflicted in direction with "
                        f"this {parent_label} wave, so none were kept."
                        if conflicted else f"no {child_label} subdivision found (no valid pivots inside this leg)."
                    ),
                ))
                continue

            offset_labels = [
                WaveLabel(
                    swing=Swing(index=w.swing.index + bar_start,
                               confirm_index=w.swing.confirm_index + bar_start,
                               price=w.swing.price, kind=w.swing.kind, label=w.swing.label),
                    wave=w.wave, sub=w.sub, direction=w.direction,
                )
                for w in chosen
            ]
            out.extend(offset_labels)
            warnings.extend(sub_warnings)
            alternates.extend(f"[{leg_label}] {a}" for a in sub_alternates)

            reached = offset_labels[-1].wave
            highest_core = max((int(w.wave) for w in offset_labels
                                if w.wave.isdigit() and int(w.wave) <= 5), default=0)
            matches = (role == "impulse" and highest_core == 5) or (role == "corrective" and reached == "c")
            checks.append(_LegHierarchyCheck(
                end_wave, role, bar_start, bar_end, minor_found=True, matches_theory=matches,
                note=f"{leg_label}: {child_label} subdivision reaches wave {reached}" + (
                    "" if matches else
                    f" -- Elliott theory expects "
                    f"{'a complete 5-wave impulse' if role == 'impulse' else 'a full A-B-C correction'} here."
                ),
            ))

    out.sort(key=lambda w: w.swing.index)
    return out, warnings, alternates, checks


# --------------------------------------------------------------------------- #
# Multi-degree (fractal) analysis
# --------------------------------------------------------------------------- #
# Traditional Elliott degree ladder, from the top level a typical backtest
# window can meaningfully represent down through as many finer levels as the
# data supports. Grand Supercycle/Supercycle/Cycle are deliberately NOT
# included -- those correspond to years/decades of real price history a
# bar-level backtest window can't represent, and forcing those labels onto a
# few weeks of intraday bars would be dishonest labeling, not real degree
# analysis. "primary"/"intermediate" keep the exact sensitivity values this
# module used historically for its original two levels (then named "primary"
# and "minor" -- "minor" was the wrong adjacent rung; the correct name for
# the level directly below Primary is Intermediate, which this ladder now
# includes explicitly). Sensitivities below that are a reasoned geometric-ish
# decay (smaller pivot window, smaller min-move threshold at each finer
# level), not empirically calibrated against real data the way some other
# constants in this codebase are -- a reasonable default, not a claim of
# precision.
DEFAULT_DEGREE_LADDER = [
    {"name": "primary",      "left": 4, "right": 4, "mm_mult": 2.00},
    {"name": "intermediate", "left": 2, "right": 2, "mm_mult": 1.00},
    {"name": "minor",        "left": 2, "right": 2, "mm_mult": 0.65},
    {"name": "minute",       "left": 1, "right": 1, "mm_mult": 0.45},
    {"name": "minuette",     "left": 1, "right": 1, "mm_mult": 0.30},
    {"name": "subminuette",  "left": 1, "right": 1, "mm_mult": 0.20},
]


def analyze_degrees(df: pd.DataFrame, degrees=None) -> dict:
    """Run analysis recursively down a ladder of degree sensitivities --
    ``DEFAULT_DEGREE_LADDER`` (traditional Elliott names) when ``degrees``
    isn't supplied, or a custom ordered list of the same
    ``{"name","left","right","mm_mult"}`` shape otherwise. The FIRST entry
    is an independent whole-chart scan (unchanged from before); every entry
    after that is nested INSIDE its immediate predecessor's own wave legs
    (see the "Degree hierarchy" section above / ``_nested_wave_sequence``),
    each level's own nested output feeding the NEXT level as its parent --
    genuinely recursive, not hardcoded to exactly two levels. Recursion
    stops early, before exhausting the ladder, the moment a level produces
    no subdivisions at all (nothing left to nest a finer level into) --
    "recursive until no smaller valid wave exists," not a fixed depth.

    The SECOND ladder entry also gets an independent, whole-chart-scan
    "<name>_global" sibling for comparison (matching the original design's
    "minor_global") -- deeper levels don't, to keep recursion cost bounded.
    """
    if degrees is None:
        degrees = DEFAULT_DEGREE_LADDER
    if not degrees:
        return {}
    med = float(np.nanmedian(atr(df["high"], df["low"], df["close"], 14)))

    top_cfg = degrees[0]
    results: dict = {
        top_cfg["name"]: analyze(df, top_cfg["left"], top_cfg["right"],
                                 top_cfg["mm_mult"] * med, top_cfg["name"]),
    }
    if len(degrees) == 1:
        return results

    parent_name = top_cfg["name"]
    parent_sequence = results[parent_name].wave_sequence
    parent_swings = identify_swings(df, top_cfg["left"], top_cfg["right"], top_cfg["mm_mult"] * med)

    for depth, cfg in enumerate(degrees[1:], start=1):
        name = cfg["name"]
        level_analysis = analyze(df, cfg["left"], cfg["right"], cfg["mm_mult"] * med, name)

        if depth == 1:
            # Independent, whole-chart-scan sibling -- identical code path
            # to the top level's own analyze() call, run over the complete
            # df, first candle to last. Saved here, before the nesting step
            # below overwrites level_analysis.wave_sequence in place --
            # otherwise this exact same result is computed and immediately
            # discarded. Kept ONLY at this one level (matching the original
            # "minor_global" design) to keep recursion cost bounded.
            results[f"{name}_global"] = replace(level_analysis, degree=f"{name}_global")

        nested_seq, nested_warn, nested_alt, checks = _nested_wave_sequence(
            df, parent_sequence, parent_swings,
            cfg["left"], cfg["right"], cfg["mm_mult"] * med,
            parent_degree_name=parent_name, child_degree_name=name,
        )
        level_analysis.wave_sequence = nested_seq
        level_analysis.warnings = level_analysis.warnings + nested_warn
        level_analysis.alternates = level_analysis.alternates + nested_alt
        level_analysis.notes = level_analysis.notes + [c.note for c in checks]
        results[name] = level_analysis

        if not nested_seq:
            break   # nothing to recurse further into -- stop the ladder here

        # Descend one more level: this level's own nested sequence becomes
        # the parent for the next one.
        parent_name = name
        parent_sequence = nested_seq
        parent_swings = identify_swings(df, cfg["left"], cfg["right"], cfg["mm_mult"] * med)

    return results


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def describe(a: WaveAnalysis) -> str:
    lines = [f"[{a.degree}]  trend={a.trend}  swings={a.n_swings}",
             f"  cycle : {a.cycle_position}",
             f"  bias  : {a.bias}"
             + (f"   invalidation<{a.invalidation:.2f}" if a.invalidation else "")]
    if a.impulse:
        P = [round(p.price, 1) for p in a.impulse.pivots]
        lines.append(f"  impulse: {a.impulse.direction} bars "
                     f"{a.impulse.start_index}->{a.impulse.end_index}  "
                     f"pivots={P}  fib_fit={a.impulse_fib['fib_fit']}")
    if a.correction:
        cf = a.correction_fib["fib_fit"] if a.correction_fib else "n/a"
        lines.append(f"  correction: {a.correction.type.value} "
                     f"bars {a.correction.start_index}->{a.correction.end_index}  fib_fit={cf}")
    if a.target_zones:
        top = sorted(a.target_zones, key=lambda z: z.strength, reverse=True)[:3]
        lines.append("  target zones: " + " | ".join(
            f"{z.center}(x{z.strength})" for z in top))
    for n in a.notes:
        lines.append(f"  note  : {n}")
    for alt in a.alternates:
        lines.append(f"  alt   : {alt}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def _ohlc_from_pivots(pivots, bars_per_leg=8, noise=0.15, seed=3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    closes = []
    for a, b in zip(pivots, pivots[1:]):
        closes.extend(np.linspace(a, b, bars_per_leg, endpoint=False))
    closes.append(pivots[-1])
    closes = np.asarray(closes) + rng.normal(0, noise, len(closes))
    return pd.DataFrame({"high": closes + rng.uniform(0.1, 0.4, len(closes)),
                         "low": closes - rng.uniform(0.1, 0.4, len(closes)),
                         "close": closes})


if __name__ == "__main__":
    # a full cycle: up-impulse 100->140, then an ABC correction down to 112
    pivots = [106, 100, 110, 104, 130, 118, 140, 122, 132, 112, 120]
    df = _ohlc_from_pivots(pivots, bars_per_leg=9)

    print("================ SINGLE-DEGREE, IN-DEPTH ================")
    med = float(np.nanmedian(atr(df["high"], df["low"], df["close"], 14)))
    print(describe(analyze(df, left=2, right=2, min_move=med, degree="intermediate")))

    print("\n================ MULTI-DEGREE (FRACTAL) ================")
    degs = analyze_degrees(df)
    for name, a in degs.items():
        print(describe(a))
        print()

    # relate degrees: how many intermediate sub-pivots fall inside the primary impulse?
    prim, inter = degs["primary"], degs["intermediate"]
    if prim.impulse:
        lo, hi = prim.impulse.start_index, prim.impulse.end_index
        subs = [s for s in identify_swings(df, 2, 2, med) if lo <= s.index <= hi]
        print(f"fractal link: primary impulse spans bars {lo}-{hi}; "
              f"intermediate degree finds {len(subs)} sub-pivots inside it")

    print("\nNOTE: candidate reads only -- confirm/invalidate with subsequent price;"
          " not financial advice.")
