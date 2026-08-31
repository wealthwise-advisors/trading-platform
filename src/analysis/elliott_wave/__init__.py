"""
Elliott Wave analysis engine (v1 core).

Built from scratch against a single approved reference,
https://elliottwave-forecast.com/elliott-wave-theory/, whose rules are
inventoried in docs/ELLIOTT_WAVE.md and specified in
docs/ELLIOTT_WAVE.md. Module layout follows
docs/ELLIOTT_WAVE.md.

WHAT THIS ENGINE SUPPORTS
-------------------------
  Impulse                    IMP-01..IMP-06
  Leading / Ending Diagonal  LD-01/03, ED-01/03
  Zigzag                     ZZ-01..ZZ-04
  Flat (generic)             FL-01, FL-02
  Running Flat               FLU-01
  Double Three               DT-01, DT-03, DT-05
  Triple Three               TT-01, TT-03, TT-05

WHAT IT DELIBERATELY DOES NOT SUPPORT
-------------------------------------
Each of these is blocked by an unresolved Open Question and is reported in
``AnalysisResult.blocked_rules`` rather than silently absent:

  Regular / Expanded Flat  OQ-09, OQ-10   "near" / "slightly" / "substantially"
                                          are never quantified
  Triangle                 OQ-12, OQ-13   no ratios, no D/E rules, no variant
                                          discriminators
  Impulse with Extension   OQ-24          "extension" has no numeric definition
  Motive Sequence          OQ-14          the sequence numbers are never stated
  Fibonacci MATCHING       OQ-05          ratios are recorded, never matched --
                                          no tolerance exists to match against
  Named wave degrees       OQ-17          pivots carry a scale index only

There is deliberately no confidence, score or probability anywhere in the
output (FR-7.4): the reference states no weighting function, so any such
number would be invented.

INDEPENDENCE
------------
This package does not import or consume ``src/analysis/swing_identification.py``
or ``src/analysis/zigzag.py`` (FR-1f.2, OQ-21 resolution). Its single shared
dependency is ``src/analysis/indicators.py::calc_rsi``, used only by
``momentum.py`` for IMP-06.
"""

from .models import (
    ELLIOTT_WAVE_ENGINE_VERSION,
    AnalysisResult,
    Direction,
    EngineConfig,
    LifecycleState,
    Pivot,
    PivotKind,
    StructureType,
    Wave,
)
from .pipeline import run_analysis
from .validation import BLOCKED_RULES, V1_LIMITATIONS, blocked_rule_ids

# D-13 rev 2 defaults (2026-08-10), calibrated on real CL/ES data against the
# gate-pass rate rather than pivot density -- see ARCHITECTURE section 5.
DEFAULT_THETA_BASE = 0.001
DEFAULT_RATIO = 4.0
DEFAULT_SCALES = 4

__all__ = [
    "ELLIOTT_WAVE_ENGINE_VERSION",
    "AnalysisResult",
    "Direction",
    "EngineConfig",
    "LifecycleState",
    "Pivot",
    "PivotKind",
    "StructureType",
    "Wave",
    "run_analysis",
    "BLOCKED_RULES",
    "V1_LIMITATIONS",
    "blocked_rule_ids",
    "DEFAULT_THETA_BASE",
    "DEFAULT_RATIO",
    "DEFAULT_SCALES",
]
