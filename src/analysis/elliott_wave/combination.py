"""
combination.py
==============

Double Three (W-X-Y) and Triple Three (W-X-Y-X-Z), reference sections 5.4/5.5.

  DT-01  3 legs, labelled W-X-Y                                     -- gates
  DT-03  W and Y are a zigzag, flat, double three or triple three
         of smaller degree                                          -- gates
  DT-04  X can be ANY corrective structure                          -- permissive
  DT-05  "Wave Y can not pass 161.8% of wave W"                     -- gates
  DT-02  "WXY is a 7 swing structure"                               -- recorded only, OQ-26

  TT-01  5 legs, labelled W-X-Y-X-Z                                 -- gates
  TT-03  W, Y and Z are a zigzag, flat, DT or TT of smaller degree  -- gates
  TT-04  both X legs can be ANY corrective structure                -- permissive
  TT-05  "Wave Y can not pass 161.8% of wave W or it can become an
         impulsive wave 3" -- note this constrains wave Y, NOT Z    -- gates
  TT-02  "WXYZ is an 11 swing structure"                            -- recorded only, OQ-26

>>> THE 161.8 CONSTANT BELOW IS A DELIBERATE, SCOPED EXCEPTION <<<
The project's TR-2 guard bans Fibonacci constants everywhere, because OQ-05 is
open and every RATIO rule is a discrete value with no stated tolerance -- so
"matching" one would require an invented tolerance. DT-05/TT-05 are different
in kind: the reference states them as an absolute prohibition ("can not pass"),
which is a one-sided INEQUALITY, not a match. An inequality needs no tolerance,
so it is implementable exactly as written. The guard is narrowed to permit
161.8 in this module only; it remains banned everywhere else.

RECURSION DEPTH -- OQ-18, resolved by project decision
------------------------------------------------------
The reference lets W/Y/Z be "a double three or triple three OF SMALLER DEGREE"
and never states a termination depth. ``max_combination_depth`` caps it at 1,
derived from what the pivot ladder can actually express rather than picked:

    corrective (zigzag/flat)      scale >= 2   needs 5-wave legs at scale 1
    DT/TT built from correctives  scale >= 3   needs correctives at scale 2
    DT/TT containing a DT/TT      scale >= 4   needs a DT at scale 3
    DT/TT nested two deep         scale >= 5   EXCEEDS the 4-scale ladder

Measured on real data across four backtest configurations (191 impulses, 73
correctives): correctives occur at scale 2 and nowhere else. So depth 1 is
exactly the ladder's expressive limit -- depth 0 would refuse a stated rule,
depth >= 2 would be dead configuration.

Expect these structures to be RARE. Scale 3 typically carries ~6 pivots and
scale 4 ~1, so a depth-1 nested combination is close to unreachable in
practice. That is a property of the ladder, not a defect here.
"""

from __future__ import annotations

from . import hierarchy
from .models import (
    LifecycleState,
    Pivot,
    StructureType,
    Wave,
)

# DT-05 / TT-05. Scoped exception to the TR-2 Fibonacci-constant ban -- see the
# module docstring. This is a stated CEILING ("can not pass"), evaluated as a
# strict inequality. It is not a ratio match and introduces no tolerance.
WAVE_Y_CEILING_OF_W = 1.618

DOUBLE_THREE_LEGS = 3
TRIPLE_THREE_LEGS = 5
_DT_LABELS = ("W", "X", "Y")
_TT_LABELS = ("W", "X", "Y", "X", "Z")

# Span kinds this module reads and writes in the shared SpanIndex.
_CORRECTIVE = "corrective"      # written by correction.py (zigzag / flat / running)
_COMBINATION = "combination"    # written here


def _wave_id(scale: int, start: int, end: int, kind: str) -> str:
    return f"s{scale}:{kind}:{start}-{end}"


def _leg_len(a: Pivot, b: Pivot) -> float:
    return abs(b.price - a.price)


def gate_wave_y_ceiling(w_start: Pivot, w_end: Pivot,
                        y_start: Pivot, y_end: Pivot) -> bool:
    """DT-05 / TT-05: wave Y must not pass 161.8% of wave W.

    Strict inequality, exactly as stated. A wave W of zero length cannot bound
    anything, so such a candidate is rejected rather than divided by zero.
    """
    len_w = _leg_len(w_start, w_end)
    if len_w == 0:
        return False
    return _leg_len(y_start, y_end) <= WAVE_Y_CEILING_OF_W * len_w


def _component_present(
    scale: int,
    a: Pivot,
    b: Pivot,
    spans: hierarchy.SpanIndex,
    depth: int,
) -> bool:
    """DT-03 / TT-03: is there a permitted component inside [a, b]?

    A zigzag/flat/running-flat at the next finer scale always qualifies. A
    DT/TT of smaller degree qualifies only when the depth cap still allows a
    further level.
    """
    if scale <= 1:
        return False
    finer = scale - 1
    if spans.contains(finer, _CORRECTIVE, a.index, b.index):
        return True
    if depth >= 1 and spans.contains(finer, _COMBINATION, a.index, b.index):
        return True
    return False


def _finer_leg_count(pivots_by_scale: dict[int, list[Pivot]],
                     scale: int, a: Pivot, b: Pivot) -> int | None:
    """Swings spanned at the next finer scale -- recorded, never gated.

    OQ-26: the reference's own arithmetic is inconsistent here. DT-02 says WXY
    is a 7-swing structure, but DT-04 says X is "any corrective structure" and
    GEN-06 says correctives move in three -- three correctives is 3+3+3 = 9,
    not 7. The stated 7 only works if X contributes a single swing. Gating on
    the count would contradict DT-04; ignoring DT-02 would drop a
    mandatory-tier statement. So it is measured and reported instead, and the
    contradiction is raised as an Open Question rather than silently resolved.
    """
    finer = pivots_by_scale.get(scale - 1)
    if not finer:
        return None
    inside = [p for p in finer if a.index <= p.index <= b.index]
    return max(0, len(inside) - 1)


def _build(
    window: list[Pivot],
    labels: tuple[str, ...],
    component_indices: tuple[int, ...],
    stype: StructureType,
    scale: int,
    depth: int,
    spans: hierarchy.SpanIndex,
    pivots_by_scale: dict[int, list[Pivot]],
) -> Wave | None:
    """Shared DT/TT construction. Returns None if any mandatory gate fails."""
    # DT-03 / TT-03 -- every component leg must hold a permitted structure
    for i in component_indices:
        if not _component_present(scale, window[i], window[i + 1], spans, depth):
            return None

    # DT-05 / TT-05 -- wave Y against wave W. Wave W is leg 0; wave Y is leg 2
    # in both DT (W X Y) and TT (W X Y X Z).
    if not gate_wave_y_ceiling(window[0], window[1], window[2], window[3]):
        return None

    # DT-04 / TT-04 -- X is permissive and never gates.

    wave = Wave(
        # NOTE: the id deliberately excludes depth. A deeper pass re-finds
        # everything a shallower one found (a corrective component still
        # matches), so keying on depth would emit each structure once per
        # pass. Depth is recorded as a measurement instead, and the caller
        # dedupes on this stable id -- first (shallowest) find wins.
        id=_wave_id(scale, window[0].index, window[-1].index, stype.value),
        scale=scale,
        start_pivot=window[0],
        end_pivot=window[-1],
        state=LifecycleState.GATED,
        structure_type=stype,
        direction=hierarchy.direction_of(window),
        measurements={
            # OQ-26: recorded, never gating
            "finer_swing_count": _finer_leg_count(
                pivots_by_scale, scale, window[0], window[-1]),
            "stated_swing_count": 7 if stype is StructureType.DOUBLE_THREE else 11,
            "wave_y_over_wave_w": (
                _leg_len(window[2], window[3]) / _leg_len(window[0], window[1])
                if _leg_len(window[0], window[1]) else None),
            "combination_depth": depth,
        },
        blocked_by=["OQ-26"],
    )
    return wave


def classify_combinations(
    pivots_by_scale: dict[int, list[Pivot]],
    spans: hierarchy.SpanIndex,
    max_depth: int = 1,
) -> list[Wave]:
    """Classify Double and Triple Threes across every scale.

    Runs AFTER correction.classify_corrections(): DT-03/TT-03 need zigzag and
    flat structures already registered in ``spans``.

    Depth passes run shallowest-first: pass 0 builds combinations from plain
    correctives, pass 1 may additionally use the pass-0 results as components.
    Each pass registers its results before the next begins, so a depth-1
    combination can see depth-0 ones but never itself.

    A structure found at depth 0 is NOT re-emitted at depth 1 -- the deeper
    pass only contributes structures that actually needed the deeper
    allowance. ``combination_depth`` therefore reports the shallowest depth at
    which a structure was reachable, which is the informative number.
    """
    out: list[Wave] = []
    seen: set[str] = set()

    for depth in range(0, max(0, max_depth) + 1):
        produced: list[Wave] = []
        for scale in sorted(pivots_by_scale):
            pivots = pivots_by_scale[scale]

            for window in hierarchy.windows(pivots, DOUBLE_THREE_LEGS):
                wave = _build(window, _DT_LABELS, (0, 2),
                              StructureType.DOUBLE_THREE, scale, depth,
                              spans, pivots_by_scale)
                if wave and wave.id not in seen:
                    _attach_legs(wave, window, _DT_LABELS, scale, out)
                    produced.append(wave)
                    seen.add(wave.id)

            for window in hierarchy.windows(pivots, TRIPLE_THREE_LEGS):
                wave = _build(window, _TT_LABELS, (0, 2, 4),
                              StructureType.TRIPLE_THREE, scale, depth,
                              spans, pivots_by_scale)
                if wave and wave.id not in seen:
                    _attach_legs(wave, window, _TT_LABELS, scale, out)
                    produced.append(wave)
                    seen.add(wave.id)

        # register this depth's results so the next pass can consume them
        for wv in produced:
            spans.add(wv.scale, _COMBINATION,
                      wv.start_pivot.index, wv.end_pivot.index)
            spans.add(wv.scale, _CORRECTIVE,
                      wv.start_pivot.index, wv.end_pivot.index)
        spans.freeze()
        out.extend(produced)

    return out


def _attach_legs(parent: Wave, window: list[Pivot], labels: tuple[str, ...],
                 scale: int, sink: list[Wave]) -> None:
    for i, label in enumerate(labels):
        leg = Wave(
            id=_wave_id(scale, window[i].index, window[i + 1].index,
                        f"{parent.id}L{i}{label}"),
            scale=scale,
            start_pivot=window[i],
            end_pivot=window[i + 1],
            state=parent.state,
            label=label,
            direction=parent.direction,
            parent_id=parent.id,
        )
        parent.child_ids.append(leg.id)
        sink.append(leg)
