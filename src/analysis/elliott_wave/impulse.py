"""
impulse.py
==========

IMP-01 .. IMP-06 (reference section 3.1).

Three gates come straight from the reference; three are project decisions
recorded in the SRS. Both kinds are marked below so the provenance is never
lost in the code:

  IMP-01  5 legs                              -- source-defined
  IMP-02  waves 1/3/5 subdivide into impulses -- source-defined (recursive)
  IMP-03  wave 2 no full retrace of wave 1    -- source-defined
  IMP-04  wave 3 not the shortest             -- DECISION (OQ-02): absolute
                                                 price distance, strict '>'
  IMP-05  wave 4 vs wave 1 price territory    -- DECISION (OQ-03): pivot-price
                                                 interval overlap, closed
  IMP-06  wave 5 momentum divergence          -- DECISION (OQ-04): RSI(13)
                                                 directional comparison

NOT implemented here, deliberately:
  * Impulse with Extension (EXT-01/02) -- OQ-24, "extension" has no numeric
    definition anywhere in the reference.
  * Any Fibonacci gate. Every ratio is a guideline and never gates (FR-4.1);
    matching is blocked on OQ-05. Ratios are recorded by measurements.py.

Gate order below is cheapest-first for performance only. It must not change
results: every gate is independent, and IMP-02/IMP-06 are evaluated last
because they are the expensive ones and the only two that can yield
UNDECIDABLE.
"""

from __future__ import annotations

import pandas as pd

from . import hierarchy, momentum
from .models import (
    Direction,
    LifecycleState,
    Pivot,
    StructureType,
    Wave,
)

IMPULSE_LEGS = 5
_LABELS = ("1", "2", "3", "4", "5")


def _wave_id(scale: int, start: int, end: int, kind: str) -> str:
    """Deterministic id -- no counters, no uuid, no clock (FR-6.1/FR-6.2)."""
    return f"s{scale}:{kind}:{start}-{end}"


# --------------------------------------------------------------------------- #
# Individual gates
# --------------------------------------------------------------------------- #
def gate_imp03(w: list[Pivot], direction: Direction) -> bool:
    """Wave 2 can't retrace more than the beginning of wave 1.

    Source-defined. Direction-aware: end of wave 2 must stay beyond the start
    of wave 1.
    """
    start_w1 = w[0].price
    end_w2 = w[2].price
    return end_w2 > start_w1 if direction is Direction.UP else end_w2 < start_w1


def gate_imp04(w: list[Pivot]) -> bool:
    """Wave 3 is not the shortest of waves 1, 3, 5.

    OQ-02 resolution (FR-3.1b.1 .. FR-3.1b.3): length is ABSOLUTE PRICE
    DISTANCE between pivot prices. Percentage, logarithmic and bar-count
    measures are explicitly rejected.

    D-02c (FR-3.1b.8): strict '>'. A wave 3 exactly equal to the shorter of
    waves 1/5 IS a shortest wave and is rejected. Reachable on tick-quantised
    data, so this boundary is deliberate, not incidental.
    """
    len1 = abs(w[1].price - w[0].price)
    len3 = abs(w[3].price - w[2].price)
    len5 = abs(w[5].price - w[4].price)
    return len3 > min(len1, len5)


def gate_imp05(w: list[Pivot]) -> bool:
    """Wave 4 does not overlap the price territory of wave 1.

    OQ-03 resolution (FR-3.1b.4 .. FR-3.1b.6): territory is the PIVOT-PRICE
    INTERVAL of each wave. Wave 4 is invalid only when its interval intersects
    wave 1's. Scanning every bar inside wave 1's span for a more extreme value
    is explicitly rejected.

    D-02c (FR-3.1b.8): closed intervals -- territories touching at exactly one
    price count as overlapping and are rejected.

    Returns True when the gate PASSES (i.e. no overlap).
    """
    lo1, hi1 = sorted((w[0].price, w[1].price))
    lo4, hi4 = sorted((w[3].price, w[4].price))
    overlaps = lo4 <= hi1 and lo1 <= hi4
    return not overlaps


def gate_imp02(
    w: list[Pivot],
    scale: int,
    spans: hierarchy.SpanIndex,
) -> bool | None:
    """Waves 1, 3 and 5 each subdivide into an impulse.

    Source-defined, and recursive. The reference never bounds the recursion.

    D-14 (ARCHITECTURE 5.3, confirmed 2026-08-09): at scale 1 there is no finer
    scale to subdivide into, so this gate CANNOT be evaluated and returns None
    (UNDECIDABLE) -- never a silent pass or fail.
    """
    if scale <= 1:
        return None
    finer = scale - 1
    for a, b in ((w[0], w[1]), (w[2], w[3]), (w[4], w[5])):
        if not spans.contains(finer, "impulse", a.index, b.index):
            return False
    return True


def gate_imp06(
    w: list[Pivot],
    direction: Direction,
    rsi: pd.Series,
) -> bool | None:
    """Wave 5 ends with momentum divergence.

    OQ-04 resolution, delegated to momentum.py. None means UNDECIDABLE
    (RSI(13) unavailable at a comparison bar), never False.
    """
    return momentum.has_divergence(
        rsi,
        wave3_index=w[3].index, wave3_price=w[3].price,
        wave5_index=w[5].index, wave5_price=w[5].price,
        direction=direction,
    )


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #
def classify_impulses(
    pivots_by_scale: dict[int, list[Pivot]],
    rsi: pd.Series,
    spans: hierarchy.SpanIndex,
) -> list[Wave]:
    """Classify impulses across every scale, finest first.

    Finest-first ordering matters: IMP-02 at scale k consults impulses already
    registered at scale k-1, so the finer scale must be complete before the
    coarser one runs.

    A candidate that fails an implementable gate is simply never created
    (FR-5.4) -- there is no INVALID state. A candidate that passes every
    evaluable gate but hits an UNDECIDABLE one is created in the UNDECIDABLE
    state with ``blocked_by`` populated, so the reason survives to the client.
    """
    out: list[Wave] = []

    for scale in sorted(pivots_by_scale):
        scale_waves: list[Wave] = []
        for w in hierarchy.windows(pivots_by_scale[scale], IMPULSE_LEGS):
            direction = hierarchy.direction_of(w)

            # cheap, fully-defined gates first
            if not gate_imp03(w, direction):
                continue
            if not gate_imp04(w):
                continue
            if not gate_imp05(w):
                continue

            blocked: list[str] = []

            sub_ok = gate_imp02(w, scale, spans)
            if sub_ok is False:
                continue
            if sub_ok is None:
                blocked.append("IMP-02")

            div_ok = gate_imp06(w, direction, rsi)
            if div_ok is False:
                continue
            if div_ok is None:
                blocked.append("IMP-06")

            state = LifecycleState.UNDECIDABLE if blocked else LifecycleState.GATED
            wave = Wave(
                id=_wave_id(scale, w[0].index, w[5].index, "imp"),
                scale=scale,
                start_pivot=w[0],
                end_pivot=w[5],
                state=state,
                structure_type=StructureType.IMPULSE,
                direction=direction,
                blocked_by=blocked,
            )
            _attach_legs(wave, w, scale, out)
            scale_waves.append(wave)

        # Register this scale's results before the next (coarser) scale runs.
        for wv in scale_waves:
            spans.add(scale, "impulse", wv.start_pivot.index, wv.end_pivot.index)
            spans.add(scale, "five_wave", wv.start_pivot.index, wv.end_pivot.index)
        spans.freeze()
        out.extend(scale_waves)

    return out


def _attach_legs(parent: Wave, w: list[Pivot], scale: int, sink: list[Wave]) -> None:
    """Create the five labelled leg waves and link them to their parent."""
    for i, label in enumerate(_LABELS):
        leg = Wave(
            id=_wave_id(scale, w[i].index, w[i + 1].index, f"imp{label}"),
            scale=scale,
            start_pivot=w[i],
            end_pivot=w[i + 1],
            state=parent.state,
            label=label,
            direction=parent.direction,
            parent_id=parent.id,
        )
        parent.child_ids.append(leg.id)
        sink.append(leg)
