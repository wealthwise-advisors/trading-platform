"""
validation.py
=============

Owns the blocked-rule registry (SRS DM-3) and the lifecycle bookkeeping that
goes with it.

This module is small on purpose but is not optional. Roughly 40 of the 94
inventoried rules cannot be implemented while their Open Question is open.
Concentrating "which rules did this build NOT evaluate, and why" in one place
is what keeps those gaps honest: the result carries them explicitly, so a
client renders a truthful "not checked" panel (FE-3.2) instead of presenting a
partial analysis as if it were complete.

Nothing here invents behaviour. It reports absence.
"""

from __future__ import annotations

from .models import AnalysisResult, LifecycleState, Wave


# Every rule this build deliberately does not evaluate, with the Open Question
# responsible. Traced to docs/ELLIOTT_WAVE_RULES.md.
BLOCKED_RULES: tuple[dict, ...] = (
    {"rules": ["IMP-F01", "IMP-F02", "IMP-F03", "IMP-F04",
               "ZZ-F01", "ZZ-F02", "FLR-F01", "FLR-F02",
               "FLE-F01", "FLE-F02", "FLU-F01", "FLU-F02",
               "DT-F01", "DT-F02", "TT-F01", "TT-F02"],
     "oq": "OQ-05",
     "reason": "Fibonacci ratios are discrete exact values with no stated "
               "tolerance; ratios are recorded but never matched."},
    {"rules": ["IMP-F02"], "oq": "OQ-06",
     "reason": "'of wave 1-2' base is undefined; ratio not computed."},
    {"rules": ["IMP-F04"], "oq": "OQ-07",
     "reason": "'inverse retracement' is never defined; that basis is skipped."},
    {"rules": ["FLR-01", "FLR-02"], "oq": "OQ-09/OQ-10",
     "reason": "Regular Flat needs 'near' and 'slightly beyond', unquantified."},
    {"rules": ["FLE-02"], "oq": "OQ-10",
     "reason": "Expanded Flat needs 'substantially beyond', unquantified; "
               "Regular and Expanded are therefore indistinguishable."},
    {"rules": ["FLR-F02", "FLE-F02", "FLU-F02"], "oq": "OQ-11",
     "reason": "Flat wave-C ratios use an undefined 'wave AB' base."},
    {"rules": ["TRI-01", "TRI-02", "TRI-03", "TRI-04",
               "TRI-05", "TRI-06", "TRI-07"], "oq": "OQ-12/OQ-13",
     "reason": "Triangle has no Fibonacci ratios, no rules for waves D/E, no "
               "variant discriminators, and a near-vacuous subdivision gate."},
    {"rules": ["MS-01", "MS-02", "MS-03"], "oq": "OQ-14",
     "reason": "Motive Sequence is defined by 'the numbers in the motive "
               "sequence', and those numbers are never stated."},
    {"rules": ["LD-02", "ED-02"], "oq": "OQ-15",
     "reason": "Wedge shape is unquantified. Overlap is measured and recorded "
               "but explicitly never gates."},
    {"rules": ["DEG-03", "DEG-04"], "oq": "OQ-17",
     "reason": "Only 2 of 9 degrees map to a timeframe and no rule assigns a "
               "degree from price data; pivots carry a scale index only."},
    {"rules": ["DT-01", "DT-02", "DT-03", "DT-04",
               "TT-01", "TT-02", "TT-03", "TT-04"], "oq": "OQ-18",
     "reason": "Double/Triple Three nest 'of smaller degree' with no depth "
               "limit and no rule for when nesting reads as one structure."},
    {"rules": ["ZZ-F03"], "oq": "OQ-19",
     "reason": "The zigzag-vs-impulse tiebreak at C=161.8% depends on "
               "'extension', which is itself undefined (OQ-24). Circular."},
    {"rules": ["GEN-04", "GEN-06"], "oq": "OQ-20",
     "reason": "A 3-swing move is both possibly-motive and possibly-corrective "
               "with no stated discriminator."},
    {"rules": ["WP-02", "WP-04", "WP-08", "WP-11", "WP-12", "WP-13", "TRI-05"],
     "oq": "OQ-22",
     "reason": "Volume statements are qualitative with no threshold, and "
               "volume is synthetic on the default data source."},
    {"rules": ["EXT-01", "EXT-02"], "oq": "OQ-24",
     "reason": "'Extension' / 'elongated' / 'exaggerated subdivisions' have no "
               "numeric definition anywhere."},
    {"rules": ["LD-03", "ED-03"], "oq": "OQ-25",
     "reason": "The reference constrains a diagonal's subdivision SHAPE "
               "(5-3-5-3-5 / 3-3-3-3-3) but never defines how detector-scale "
               "legs combine into an Elliott sub-wave. 'This sub-wave is a "
               "five-wave structure' is evaluated as 'the finer scale registers "
               "an impulse inside it' -- a reading, not a stated rule. Every "
               "grouping consistent with the stated shape is emitted as an "
               "alternate; none is preferred."},
    {"rules": ["EXT-03", "EXT-04"], "oq": "n/a (not implementable)",
     "reason": "Market-class priors need an instrument taxonomy this platform "
               "lacks and probability values the reference never gives."},
)


# Known v1 scope limitations that are NOT reference gaps -- they are
# consequences of this build's own ordering or coverage.
V1_LIMITATIONS: tuple[str, ...] = (
    "Diagonals are detected only in impulse wave 1 / wave 5 host positions. "
    "Zigzag wave A/C hosts (also valid per LD-01/ED-01) are not searched, "
    "because corrections are classified after diagonals in the pipeline.",
    "IMP-02 and the correction five-wave gates cannot be evaluated at scale 1 "
    "(no finer scale exists). Candidates there are UNDECIDABLE, never passed "
    "or failed (D-14).",
)


def blocked_rule_report() -> list[dict]:
    """The registry as plain dicts, safe to serialize."""
    return [dict(entry) for entry in BLOCKED_RULES]


def blocked_rule_ids() -> set[str]:
    ids: set[str] = set()
    for entry in BLOCKED_RULES:
        ids.update(entry["rules"])
    return ids


def summarize(result: AnalysisResult, waves: list[Wave]) -> None:
    """Attach the registry and a lifecycle census to the result, in place."""
    result.blocked_rules = blocked_rule_report()
    result.notes.extend(V1_LIMITATIONS)

    census = {state.value: 0 for state in LifecycleState}
    for w in waves:
        census[w.state.value] += 1
    result.config["lifecycle_census"] = census
