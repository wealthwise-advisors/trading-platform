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
"""

from __future__ import annotations

from .models import StructureType, Wave


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


def _record_zigzag(s: Wave, by_id: dict[str, Wave]) -> None:
    legs = _legs(s, by_id)
    if len(legs) != 3:
        return
    wa, wb, wc = legs
    s.measurements.update({
        "ZZ-F01_waveB_over_waveA": _ratio(wb.length, wa.length),
        "ZZ-F02_waveC_over_waveA": _ratio(wc.length, wa.length),
    })
