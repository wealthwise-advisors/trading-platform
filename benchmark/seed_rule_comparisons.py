"""Seeds rule_comparisons with the ONE genuine, sourced, inspectable
community reference found for this benchmark: an open-source TradingView
Pine Script (Gabremoku, 'Elliott Wave - Impulse Strategy', public on
GitHub). Exact thresholds below were fetched and read directly from the
script's source, not inferred or guessed -- see reference_sources.source_url.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.db import init_db, connect, new_id

COMPARISONS = [
    {
        "rule_name": "Wave 2 retracement gate",
        "engine_rule": "Continuous range (0.382, 0.851) of Wave 1 -- any ratio in that open interval passes; "
                       "0.382/0.618 specifically also earn the 'sub=1' fib+pattern confidence flag.",
        "reference_rule": "Discrete allowed set {0.50, 0.618, 0.764, 0.854} ONLY, each with a user-configurable "
                          "+/-10% (default) tolerance band -- a ratio between two allowed values (e.g. 0.70) is "
                          "REJECTED outright, not merely scored lower.",
        "agreement": "not_comparable",
    },
    {
        "rule_name": "Wave 2 hard invalidation (100%+ retracement)",
        "engine_rule": "Hard rule: retrace2 must be strictly < 1.0 (never retraces to or past the origin).",
        "reference_rule": "Not explicitly checked in this script -- no code path validates Wave 2 against the "
                          "origin at all; only the discrete ratio-set check above applies.",
        "agreement": "engine_stricter",
    },
    {
        "rule_name": "Wave 3 extension validation",
        "engine_rule": "Hard rule: Wave 3 must exceed Wave 1 (sign*(w3-w1)>0); soft Fibonacci band "
                       "(1.618-2.618) for confidence scoring only.",
        "reference_rule": "No explicit Wave 3 validation found in this script's source at all.",
        "agreement": "engine_stricter",
    },
    {
        "rule_name": "Wave 4 overlap rule",
        "engine_rule": "Hard rule: Wave 4 must NOT enter Wave 1's price territory (universal Elliott rule).",
        "reference_rule": "No explicit overlap check found in this script's source.",
        "agreement": "engine_stricter",
    },
    {
        "rule_name": "Wave 3 not-shortest rule",
        "engine_rule": "Hard rule: Wave 3 must never be the shortest of Waves 1, 3, 5.",
        "reference_rule": "No explicit check found in this script's source.",
        "agreement": "engine_stricter",
    },
    {
        "rule_name": "Swing/pivot detection sensitivity",
        "engine_rule": "N-bar fractal, left/right configurable (default 2/2), PLUS an adaptive local-context "
                       "filter (local ATR, recent volatility, prior-swing fraction) on top of a raw min_move floor.",
        "reference_rule": "zigzagLength = 2-bar minimum lookback -- a raw fractal-style pivot detector with no "
                          "documented adaptive/local-context filtering found in the fetched source.",
        "agreement": "engine_stricter",
    },
]


def seed():
    init_db()
    with connect() as conn:
        for c in COMPARISONS:
            conn.execute(
                "INSERT INTO rule_comparisons (rule_comparison_id, source_id, rule_name, engine_rule, reference_rule, agreement) "
                "VALUES (?,?,?,?,?,?)",
                (new_id("rulecmp"), "tv_gabremoku", c["rule_name"], c["engine_rule"], c["reference_rule"], c["agreement"]),
            )
    print(f"seeded {len(COMPARISONS)} rule comparisons")


if __name__ == "__main__":
    seed()
