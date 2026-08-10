"""
measurements.py
===============

Records the reference's guideline ratios. Computes; never matches.

>>> THIS MODULE EXPOSES NO COMPARISON, TOLERANCE, OR MATCH FUNCTION. <<<
That absence is the enforcement mechanism for OQ-05 and is asserted by TR-2.

Why: every Fibonacci relationship in the reference is a DISCRETE EXACT VALUE
("50%, 61.8%, 76.4%, or 85.4%"), never a band, and no tolerance is stated
anywhere on the page. Exact float equality never matches real price data, so
declaring a ratio "matched" would require inventing a tolerance. Until OQ-05
is answered, the honest output is the raw ratio and nothing more.

Ratios ARE computed where the base is unambiguous, and deliberately skipped
where it is not:

  computed   IMP-F01  wave 2 / wave 1
  computed   IMP-F03  wave 4 / wave 3
  computed   IMP-F04  wave 5 / wave 1            (the "equal to wave 1" basis)
  computed   IMP-F04  wave 5 / net(wave 1..3)    (the "61.8% of wave 1-3" basis)
  computed   ZZ-F01   wave B / wave A
  computed   ZZ-F02   wave C / wave A

  SKIPPED    IMP-F02  wave 3 / "wave 1-2"  -- OQ-06: is the base the net
                                              displacement start-of-1 to
                                              end-of-2, or wave 1's length
                                              projected from end-of-2? The
                                              reference does not say.
  SKIPPED    IMP-F04  "inverse 123.6-161.8% retracement of wave 4"
                                           -- OQ-07: "inverse retracement" is
                                              used but never defined.
  SKIPPED    flat wave C / "wave AB"       -- OQ-11: "wave AB" is undefined
                                              (net A-to-B? len(A)+len(B)?
                                              len(A)?).

Skipping is not an omission -- validation.py reports each skipped rule so the
gap is visible to the client rather than inferred.

EXTENSION (EXT-01, EXT-02) -- MEASURED, NEVER CLASSIFIED
--------------------------------------------------------
``record_extension`` records which motive wave is longest, by how much, and
how many finer-scale legs each motive wave contains. It does NOT decide
whether a structure "has an extension", and ``StructureType`` deliberately has
no ``IMPULSE_WITH_EXTENSION`` member, so GEN-03's three-way motive
classification stays unavailable.

Why measurement only -- OQ-24 was investigated on real data and stayed open:

  * The reference gives no numeric definition of "extended". Unlike DT-05
    ("can not pass 161.8% of wave W") there is no stated inequality to lift,
    so this is NOT a tolerance problem and is independent of OQ-05.
  * Five candidate formulations were measured over 1,142 impulses (longest /
    second-longest, w3/w1, longest / mean of the other two, longest / total,
    longest / shortest). Every one is a smooth monotone decay -- no cliff, no
    second mode, nothing resembling the discontinuity D-13 was calibrated
    against. Any cutoff would be a chosen hit-rate wearing calibration's
    clothes.
  * EXT-02 is conjunctive -- "elongated impulses WITH exaggerated
    subdivisions". Subdivision count is unmeasurable on 98.7% of impulses
    (they confirm at scale 1, where no finer scale exists, D-14), and on the
    remainder the two criteria point at DIFFERENT waves 36% of the time.
  * Defining extension as 161.8% would make OQ-19 circular: the reference
    offers "whether the third swing has extension" as the tiebreak for a
    zigzag wave C at 161.8% of A. It would also collide with IMP-F02, which
    lists 161.8% as the FIRST, typical value for an ordinary wave 3.

So the ratio is reported and the judgement is left to the client. Every
structure carrying these measurements also carries ``blocked_by: ["OQ-24"]``.
"""

from __future__ import annotations

from .models import Pivot, StructureType, Wave

#: 5-leg motive structures. EXT-01 names impulses only; the diagonals are
#: measured too because they are the reference's other 5-leg motive forms
#: (GEN-03), and a measurement asserts nothing the source did not say. Only
#: ``EXT-01_*`` on an impulse corresponds to a reference statement.
_MOTIVE_5 = (
    StructureType.IMPULSE,
    StructureType.LEADING_DIAGONAL,
    StructureType.ENDING_DIAGONAL,
)

#: Positions of waves 1, 3 and 5 within a 5-leg motive structure.
_MOTIVE_POSITIONS = ((0, "1"), (2, "3"), (4, "5"))


def _ratio(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _legs(structure: Wave, by_id: dict[str, Wave]) -> list[Wave]:
    return [by_id[cid] for cid in structure.child_ids if cid in by_id]


def record(structures: list[Wave], by_id: dict[str, Wave]) -> None:
    """Attach raw guideline ratios to each structure, in place.

    No structure is accepted or rejected here -- FR-4.1: guideline
    measurements are recorded and NEVER gate.
    """
    for s in structures:
        if s.structure_type is StructureType.IMPULSE:
            _record_impulse(s, by_id)
        elif s.structure_type is StructureType.ZIGZAG:
            _record_zigzag(s, by_id)
        # Flat ratios all use the undefined "wave AB" base (OQ-11) -- nothing
        # computable, so nothing recorded.


def _record_impulse(s: Wave, by_id: dict[str, Wave]) -> None:
    legs = _legs(s, by_id)
    if len(legs) != 5:
        return
    w1, w2, _w3, w4, w5 = legs
    net_1_3 = abs(legs[2].end_pivot.price - w1.start_pivot.price)

    s.measurements.update({
        "IMP-F01_wave2_over_wave1": _ratio(w2.length, w1.length),
        "IMP-F03_wave4_over_wave3": _ratio(w4.length, legs[2].length),
        "IMP-F04_wave5_over_wave1": _ratio(w5.length, w1.length),
        "IMP-F04_wave5_over_net_1_3": _ratio(w5.length, net_1_3),
    })


def record_extension(
    structures: list[Wave],
    by_id: dict[str, Wave],
    by_scale: dict[int, list[Pivot]],
) -> None:
    """Record EXT-01/EXT-02 quantities on every 5-leg motive structure.

    Measurement only (FR-4.1). Nothing here gates, and no structure is
    reclassified: ``StructureType`` has no ``IMPULSE_WITH_EXTENSION`` member
    precisely because no threshold exists to justify emitting one.

    Every structure touched gains ``blocked_by: ["OQ-24"]`` so a client
    reading ``EXT-01_longest_over_second`` cannot mistake it for a verdict.
    """
    for s in structures:
        if s.structure_type not in _MOTIVE_5:
            continue
        legs = _legs(s, by_id)
        if len(legs) != 5:
            continue

        lengths = {label: legs[i].length for i, label in _MOTIVE_POSITIONS}
        ordered = sorted(lengths.values(), reverse=True)

        s.measurements.update({
            "EXT-01_motive_wave_lengths": dict(lengths),
            "EXT-01_longest_motive_wave": _sole_max(lengths),
            "EXT-01_longest_over_second": _ratio(ordered[0], ordered[1]),
        })
        s.measurements.update(_subdivision_measurements(s, legs, by_scale))

        if "OQ-24" not in s.blocked_by:
            s.blocked_by.append("OQ-24")


def _sole_max(values: dict[str, float]) -> str | None:
    """The single largest entry, or None when two or more tie.

    Reject-on-tie, consistent with D-02c. A tie means the reference's "one of
    the motive waves" has no unique referent, and reporting an arbitrary
    winner would invent a resolution the data does not supply.
    """
    peak = max(values.values())
    winners = [k for k, v in values.items() if v == peak]
    return winners[0] if len(winners) == 1 else None


def _subdivision_measurements(
    s: Wave,
    legs: list[Wave],
    by_scale: dict[int, list[Pivot]],
) -> dict:
    """EXT-02's second criterion, where a finer scale exists to measure it.

    At scale 1 there is no finer scale, so subdivision count is unmeasurable
    by construction (D-14) -- reported as None rather than as zero, which
    would read as "measured, and it has none".
    """
    finer = s.scale - 1
    pivots = by_scale.get(finer) if finer >= 1 else None
    if not pivots:
        return {
            "EXT-02_subdivision_counts": None,
            "EXT-02_most_subdivided_wave": None,
            "EXT-02_criteria_agree": None,
        }

    counts = {}
    for i, label in _MOTIVE_POSITIONS:
        leg = legs[i]
        inside = sum(1 for p in pivots
                     if leg.start_pivot.index <= p.index <= leg.end_pivot.index)
        counts[label] = max(0, inside - 1)      # legs between pivots, not pivots

    if not any(counts.values()):
        return {
            "EXT-02_subdivision_counts": counts,
            "EXT-02_most_subdivided_wave": None,
            "EXT-02_criteria_agree": None,
        }

    most = _sole_max(counts)
    longest = s.measurements.get("EXT-01_longest_motive_wave")
    agree = None if (most is None or longest is None) else (most == longest)
    return {
        "EXT-02_subdivision_counts": counts,
        "EXT-02_most_subdivided_wave": most,
        # EXT-02 is conjunctive. When the two criteria name different waves the
        # rule cannot be satisfied as written -- recorded, never resolved.
        "EXT-02_criteria_agree": agree,
    }


def _record_zigzag(s: Wave, by_id: dict[str, Wave]) -> None:
    legs = _legs(s, by_id)
    if len(legs) != 3:
        return
    wa, wb, wc = legs
    s.measurements.update({
        "ZZ-F01_waveB_over_waveA": _ratio(wb.length, wa.length),
        "ZZ-F02_waveC_over_waveA": _ratio(wc.length, wa.length),
    })
