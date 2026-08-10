"""
models.py
=========

Immutable data types shared by every module in this package. No logic.

Per ARCHITECTURE §6.1 this is the dependency leaf: it imports nothing from
the package.

Two absences are deliberate and load-bearing:

* ``Wave`` has NO ``confidence`` / ``score`` / ``probability`` field.
  SRS FR-7.4: the reference states no weighting function anywhere -- every
  ratio is given standalone with no rule for combining ratios into a single
  number. Emitting one would be invention. Guarded by TR-4.

* ``Wave`` has NO ``valid`` / ``violated_rules`` field.
  SRS FR-5.4: a candidate that fails an implementable gate is never
  constructed, so there is nothing for such a field to describe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


ELLIOTT_WAVE_ENGINE_VERSION = "0.1.0-core"


class PivotKind(str, Enum):
    HIGH = "H"
    LOW = "L"


class LifecycleState(str, Enum):
    """SRS FR-5.2 / FR-5.3.

    There is deliberately no INVALID/REJECTED state (FR-5.4).
    UNDECIDABLE exists because with several rules still blocked, a candidate
    can be genuinely neither valid nor invalid -- collapsing that into either
    would misreport.
    """

    ENUMERATED = "enumerated"      # window formed, nothing checked yet
    GATED = "gated"                # passed every implementable mandatory gate
    MEASURED = "measured"          # guideline measurements recorded
    UNDECIDABLE = "undecidable"    # a required gate could not be evaluated


class StructureType(str, Enum):
    """Only the reference's named structures (SRS DM-4).

    Deferred and therefore absent: impulse_with_extension (OQ-24),
    flat_regular / flat_expanded (OQ-09/OQ-10), triangle (OQ-12/OQ-13),
    motive_sequence (OQ-14).

    double_three / triple_three were added once OQ-18 was resolved by capping
    recursion depth (see combination.py).
    """

    IMPULSE = "impulse"
    LEADING_DIAGONAL = "leading_diagonal"
    ENDING_DIAGONAL = "ending_diagonal"
    ZIGZAG = "zigzag"
    FLAT = "flat"
    FLAT_RUNNING = "flat_running"
    DOUBLE_THREE = "double_three"
    TRIPLE_THREE = "triple_three"


class Direction(str, Enum):
    UP = "up"
    DOWN = "down"


@dataclass(frozen=True)
class Pivot:
    """A confirmed price turning point (SRS DM-1).

    ``index`` is the bar where the extreme occurred. ``confirm_index`` is the
    later bar at which the reversal confirmed it. They are distinct on purpose:
    a consumer evaluating bar t may only use pivots with confirm_index <= t
    (FR-1b.2). Using ``index`` as if the pivot were known then is look-ahead
    bias.

    ``price`` is the bar's own extreme -- high for a HIGH pivot, low for a LOW
    pivot (FR-1c.1). This is the single pivot-price convention used by IMP-04,
    IMP-05 and IMP-06 alike.

    ``scale`` identifies which threshold in the ladder produced this pivot. It
    is NOT an Elliott degree -- mapping scales to the reference's 9 named
    degrees is OQ-17, still open (FR-1d.3).
    """

    index: int
    confirm_index: int
    timestamp: object
    price: float
    kind: PivotKind
    scale: int


@dataclass
class Wave:
    """One labelled leg or one complete structure (SRS DM-2)."""

    id: str
    scale: int
    start_pivot: Pivot
    end_pivot: Pivot
    state: LifecycleState = LifecycleState.ENUMERATED
    label: Optional[str] = None
    structure_type: Optional[StructureType] = None
    direction: Optional[Direction] = None
    parent_id: Optional[str] = None
    child_ids: list[str] = field(default_factory=list)
    measurements: dict = field(default_factory=dict)
    blocked_by: list[str] = field(default_factory=list)

    @property
    def length(self) -> float:
        """Absolute price distance (OQ-02 resolution, FR-3.1b.1)."""
        return abs(self.end_pivot.price - self.start_pivot.price)

    @property
    def territory(self) -> tuple[float, float]:
        """Pivot-price interval (OQ-03 resolution, FR-3.1b.4)."""
        a, b = self.start_pivot.price, self.end_pivot.price
        return (a, b) if a <= b else (b, a)


@dataclass(frozen=True)
class EngineConfig:
    """Pivot ladder configuration -- D-13 rev 2, 2026-08-10.

    Values calibrated against real CL and ES data plus the deterministic
    synthetic generator; see ARCHITECTURE section 5. Configuration, not rules,
    and tunable per call.

    REVISION HISTORY
    ----------------
    rev 1 (2026-08-09): theta_base=0.002, ratio=2.5. Calibrated on pivot
        DENSITY. Superseded: running the engine showed that ladder can never
        satisfy IMP-02's recursive subdivision requirement, so no impulse ever
        reached GATED above scale 1.
    rev 2 (2026-08-10): theta_base=0.001, ratio=4.0. Calibrated on the real
        binding constraint -- whether a coarse leg contains a finer window that
        passes ALL SIX impulse gates (~6% pass rate), not merely >=5 finer
        pivots (~24%).
    """

    theta_base: float = 0.001   # 0.10%  -- ladder: 0.10 / 0.40 / 1.60 / 6.40 %
    ratio: float = 4.0
    scales: int = 4
    rsi_period: int = 13        # IMP-06, OQ-04 resolution (FR-3.1a.2)
    # OQ-18 resolution. 1 is the ladder's expressive limit, not a guess:
    # correctives occur only at scale 2, so a combination needs scale 3 and a
    # nested combination scale 4 -- two levels would need scale 5. See
    # combination.py.
    max_combination_depth: int = 1

    def thresholds(self) -> list[float]:
        return [self.theta_base * (self.ratio ** k) for k in range(self.scales)]


@dataclass
class AnalysisResult:
    """Top-level engine output (SRS DM-3)."""

    engine_version: str
    config: dict
    pivots: list[Pivot] = field(default_factory=list)
    waves: list[Wave] = field(default_factory=list)
    blocked_rules: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    # Windows satisfying TRI-01 and TRI-03, measured but never classified.
    # Deliberately NOT in `waves`: they are not structures, and OQ-12/OQ-13
    # keep them unnameable. See triangle.py.
    triangle_candidates: list[dict] = field(default_factory=list)
