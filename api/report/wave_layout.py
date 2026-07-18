"""
wave_layout.py
==============

Static-report port of web/src/lib/waveLabelLayout.ts's tier + collision
logic. The exported HTML report is a fixed snapshot -- there's no React
onRelayout to re-run decluttering as the user zooms, so this renders at ONE
fixed detail level (Core + Secondary tier) chosen to read well as a static
image, with the same genuine 2D (time-and-price) collision pass so labels
never overlap. The connecting line/marker trace is tier-filtered the same
way, so the exported chart shows a clean backbone rather than every pivot.

Keep tier/priority rules in sync with waveLabelLayout.ts if either changes.
"""

from __future__ import annotations

from typing import Iterable, List, TypedDict

CORE_WAVES = {"1", "3", "5", "a", "c"}
SECONDARY_WAVES = {"2", "4", "b"}

# Static export shows Core + Secondary by default -- richer than the live
# app's own zoomed-out default (Core only), since a static image has no
# interactive path to reveal more detail the way zooming does live.
DEFAULT_ALLOWED_TIERS = frozenset({0, 1})


def tier_of(wave: str) -> int:
    if wave in CORE_WAVES:
        return 0
    if wave in SECONDARY_WAVES:
        return 1
    return 2  # continuation 6..11


def priority_of(wave: str, sub: int | None) -> float:
    tier = tier_of(wave)
    tier_score = (2 - tier) * 10
    sub_score = 2 if sub == 1 else (0.5 if sub == 2 else 1)
    return tier_score + sub_score


class WaveItem(TypedDict):
    t: float        # epoch seconds
    price: float
    wave: str
    sub: int | None
    kind: str        # "high" | "low"


MIN_SPACING_T_FRACTION = 0.022
MIN_SPACING_P_FRACTION = 0.045


def declutter_static(
    items: List[WaveItem],
    t_span: float,
    p_span: float,
    allowed_tiers: Iterable[int] = DEFAULT_ALLOWED_TIERS,
) -> List[WaveItem]:
    """Same-lane (high/low), genuine 2D (time AND price) collision pass --
    a candidate is only rejected if it's close to an already-placed label on
    BOTH axes, matching real text-box overlap geometry (far apart on either
    axis alone means the boxes don't actually overlap on screen)."""
    tiers = set(allowed_tiers)
    t_span = t_span or 1.0
    p_span = p_span or 1e-9
    in_tier = [it for it in items if tier_of(it["wave"]) in tiers]
    by_priority = sorted(in_tier, key=lambda it: (-priority_of(it["wave"], it["sub"]), it["t"]))

    lanes: dict[str, List[WaveItem]] = {"high": [], "low": []}
    shown: List[WaveItem] = []
    for cand in by_priority:
        lane = lanes[cand["kind"]]
        collides = any(
            abs(p["t"] - cand["t"]) / t_span < MIN_SPACING_T_FRACTION
            and abs(p["price"] - cand["price"]) / p_span < MIN_SPACING_P_FRACTION
            for p in lane
        )
        if not collides:
            lane.append(cand)
            shown.append(cand)
    shown.sort(key=lambda it: it["t"])
    return shown


def tier_filter_run(run: List[WaveItem], allowed_tiers: Iterable[int] = DEFAULT_ALLOWED_TIERS) -> List[WaveItem]:
    """Filters a run's points to the allowed tiers for the connecting line/
    marker trace. Falls back to endpoints if a run has none (shouldn't
    normally happen -- every run starts at Wave 1, which is Core)."""
    tiers = set(allowed_tiers)
    filtered = [w for w in run if tier_of(w["wave"]) in tiers]
    if filtered:
        return filtered
    return [run[0], run[-1]] if run else []
