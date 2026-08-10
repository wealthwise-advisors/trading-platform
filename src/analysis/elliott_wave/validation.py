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
    # 14 rules, not 16. FLE-F02 and FLU-F02 were dropped 2026-08-10: the
    # reference states those two as RANGES ("123.6% - 161.8%", "61.8% - 100%"),
    # and a range is directly evaluable with no tolerance at all. They stay
    # blocked, but by OQ-11's undefined "wave AB" base, not by OQ-05.
    {"rules": ["IMP-F01", "IMP-F02", "IMP-F03", "IMP-F04",
               "ZZ-F01", "ZZ-F02", "FLR-F01", "FLR-F02",
               "FLE-F01", "FLU-F01",
               "DT-F01", "DT-F02", "TT-F01", "TT-F02"],
     "oq": "OQ-05",
     "reason": "Fibonacci ratios are discrete exact values with no stated "
               "tolerance; ratios are recorded but never matched. "
               "Investigated 2026-08-10 and left open on three independent "
               "grounds: the reference states no tolerance anywhere AND "
               "demonstrably writes an explicit range where it means one (3 "
               "rules do), so the discrete lists are discrete by intent; real "
               "ratios show no clustering on the stated values once the data's "
               "own density is controlled for (0 of 5 families significant); "
               "and the width needed to match half the observations varies "
               "11-fold across families, so no single global tolerance could "
               "serve them."},
    {"rules": ["IMP-F02"], "oq": "OQ-06",
     "reason": "'of wave 1-2' base is undefined; ratio not computed."},
    # IMP-F04 carries OQ-05 as well: of its three stated bases, only the
    # "inverse 123.6-161.8% retracement" one is undefined here. The other two
    # ("equal to wave 1", "61.8% of wave 1-3") are discrete values and are
    # blocked by OQ-05 like every other discrete ratio.
    {"rules": ["IMP-F04"], "oq": "OQ-07",
     "reason": "'inverse retracement' is never defined; that basis is skipped. "
               "The rule's other two bases are discrete and blocked by OQ-05."},
    {"rules": ["FLR-01", "FLR-02"], "oq": "OQ-09/OQ-10",
     "reason": "Regular Flat needs 'near' and 'slightly beyond', unquantified. "
               "Investigated on 356 real flats 2026-08-10 and left open: wave "
               "B's retracement of wave A runs continuously THROUGH 1.00 with "
               "no trough (p25 0.37, p50 0.65, p75 1.21; only 9% land within "
               "+/-10% of 1.00), so 'near' has no natural width. Regular Flat "
               "has NO exact criterion of its own -- both its statements are "
               "vague -- so it cannot be gated at all. The quantities are "
               "recorded (FLR-01_*, FLR-02_*); only the verdict is withheld."},
    {"rules": ["FLE-02"], "oq": "OQ-10",
     "reason": "Expanded Flat's wave C needs 'substantially beyond', "
               "unquantified. Investigated 2026-08-10: where wave C lands "
               "relative to wave A's end is a broad continuum (p5 0.17 to p95 "
               "5.98 times |A|) with every large gap out at p97+, so no "
               "threshold separates 'slightly' from 'substantially'. NOTE "
               "FLE-01 -- 'wave B terminates beyond the STARTING level of "
               "wave A' -- needs no threshold and IS measured; whether it may "
               "gate is an open project decision, not a blocked rule."},
    {"rules": ["FLR-F02", "FLE-F02", "FLU-F02"], "oq": "OQ-11",
     "reason": "Flat wave-C ratios use an undefined 'wave AB' base."},
    {"rules": ["TRI-01", "TRI-02", "TRI-03", "TRI-04",
               "TRI-05", "TRI-06", "TRI-07"], "oq": "OQ-12/OQ-13",
     "reason": "Triangle states no Fibonacci ratio, no rule for wave D or "
               "wave E, and no geometry for its four named variants -- those "
               "appear only in a graphic, never in prose, so there is no text "
               "to extract. CORRECTED 2026-08-10: the subdivision gate is NOT "
               "'near-vacuous' as previously recorded. TRI-01 + TRI-03 are "
               "exact, mandatory-tier and selective -- 328 of 3,912 five-leg "
               "windows pass (8.4%), comparable to the flat and zigzag "
               "confirm rates. They still do not gate: the strict reading of "
               "'subdivided into three' finds 1 candidate in 3,912 so the "
               "loose one is used and OQ-25 is inherited; TRI-02's host rule "
               "is guideline-tier and matches only 6 of 328 anyway; and 21% "
               "of candidates are plainly trending, which would contradict "
               "the reference's own opening definition of the word. "
               "Candidates are measured instead -- see triangle.py."},
    {"rules": ["MS-01", "MS-02", "MS-03"], "oq": "OQ-14",
     "reason": "Motive Sequence is defined by 'the numbers in the motive "
               "sequence', and those numbers are never stated."},
    {"rules": ["LD-02", "ED-02"], "oq": "OQ-15",
     "reason": "Wedge shape is unquantified. Overlap is measured and recorded "
               "but explicitly never gates."},
    {"rules": ["DEG-03", "DEG-04"], "oq": "OQ-17",
     "reason": "Only 2 of 9 degrees map to a timeframe and no rule assigns a "
               "degree from price data; pivots carry a scale index only."},
    {"rules": ["DT-02", "TT-02"], "oq": "OQ-26",
     "reason": "The reference's own swing arithmetic is inconsistent: DT-02 "
               "says WXY is a 7-swing structure, but DT-04 says X is 'any "
               "corrective structure' and GEN-06 says correctives move in "
               "three -- 3+3+3 is 9, not 7. The stated count only works if X "
               "is a single swing. Swing count is recorded as a measurement "
               "and never gated, so neither statement is silently discarded."},
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
               "numeric definition anywhere. Investigated on real data and "
               "left open: across 1,142 impulses, five candidate measures all "
               "decay smoothly with no cliff, so any cutoff would be a chosen "
               "hit-rate rather than a calibration. EXT-02's subdivision "
               "criterion is unmeasurable on 98.7% of impulses and names a "
               "different wave than length does on 36% of the rest. The "
               "quantities ARE recorded (EXT-01_*, EXT-02_*); only the verdict "
               "is withheld, and no impulse_with_extension type is emitted."},
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
    "Double/Triple Three recursion is capped at depth 1 (OQ-18 resolution) -- "
    "the pivot ladder's expressive limit, since correctives occur only at "
    "scale 2. Depth-1 nesting is reachable in principle but close to "
    "unreachable in practice, because scale 3 carries few pivots and scale 4 "
    "almost none.",
    "Diagonals are detected only in impulse wave 1 / wave 5 host positions. "
    "Zigzag wave A/C hosts (also valid per LD-01/ED-01) are not searched, "
    "because corrections are classified after diagonals in the pipeline.",
    "IMP-02 and the correction five-wave gates cannot be evaluated at scale 1 "
    "(no finer scale exists). Candidates there are UNDECIDABLE, never passed "
    "or failed (D-14). How many impulses escape this depends on how much data "
    "is analysed, not on the rule: at <=7,189 bars no impulse ever confirmed "
    "above scale 1, but over 60,000-bar slices 14 GATED scale-2 impulses "
    "appear. Small samples will still show none.",
    "Triangle candidates are measured but never classified -- OQ-12 and OQ-13 "
    "are open. TRI-01/TRI-03 are exact and would be gateable if 'sideways' "
    "were ever quantified, but it is not, so no TRIANGLE structure type "
    "exists. See triangle.py and AnalysisResult.triangle_candidates.",
    "Regular and Expanded Flat are measured but never separated -- OQ-09 and "
    "OQ-10 are open and neither 'near', 'slightly beyond' nor "
    "'substantially beyond' has a natural width in the data. Flats stay "
    "generically typed. See measurements.record_flat_subtype.",
    "Extension (EXT-01/EXT-02) is measured but never classified -- OQ-24 is "
    "open and no threshold for 'extended' exists in the reference or in the "
    "data. See measurements.record_extension.",
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
