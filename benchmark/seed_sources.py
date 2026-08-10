"""Seeds reference_sources with ALL seven sources the task requires --
including the ones with NO real access, documented honestly rather than
omitted. This table is itself a key deliverable: it's the record of what
was actually checked and what was found, not just an assumption.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.db import init_db, connect

SOURCES = [
    # -- Commercial: checked, no path to genuine access --
    {
        "source_id": "motivewave", "category": "commercial", "name": "MotiveWave",
        "access_status": "NO_ACCESS",
        "access_notes": (
            "MotiveWave is licensed desktop software with no public API or published "
            "output database. There is no way to obtain 'what MotiveWave says about "
            "chart X' without a licensed installation and a human operating it. Not "
            "fabricated. Closing this gap requires a MotiveWave license and a human "
            "to run it and record results into benchmark_charts/expected_primary_count_json."
        ),
        "source_url": None,
    },
    {
        "source_id": "elwave", "category": "commercial", "name": "ELWAVE",
        "access_status": "NO_ACCESS",
        "access_notes": "Same situation as MotiveWave -- licensed desktop software, no public output data, no API.",
        "source_url": None,
    },
    # -- Community: one genuine, sourced, inspectable result found --
    {
        "source_id": "tv_gabremoku", "category": "community",
        "name": "TradingView community script (Gabremoku, 'Elliott Wave - Impulse Strategy', open-source Pine)",
        "access_status": "RULE_LEVEL_ONLY",
        "access_notes": (
            "This specific script's Pine source is public on GitHub -- its exact "
            "validation thresholds were fetched and read directly (see source_url), "
            "not inferred. This enables a genuine RULE-LEVEL comparison (does its "
            "documented Wave 2 ratio gate, error tolerance, etc. match this engine's), "
            "but NOT a per-chart output comparison -- I cannot execute Pine Script or "
            "access live TradingView chart data from this environment, so I have no "
            "way to obtain 'what this script outputs on chart X.' Most other "
            "TradingView Elliott Wave scripts found (LuxAlgo, UAlgo, etc.) are "
            "closed-source/protected even though publicly listed -- their exact logic "
            "isn't inspectable at all, so they are not included as if they were."
        ),
        "source_url": "https://github.com/hasnocool/tradingview-pine-scripts/blob/main/Elliot%20Wave%20-%20Impulse%20Strategy.pine",
    },
    {
        "source_id": "ewf_public", "category": "community", "name": "ElliottWaveForecast public analyses",
        "access_status": "NO_ACCESS",
        "access_notes": (
            "ElliottWaveForecast's specific published chart analyses are a paid "
            "subscription product; free/preview content is not a stable, citable "
            "dataset of exact wave counts on specific charts, and using cached/scraped "
            "proprietary analysis would misrepresent both licensing and currency. Not accessed."
        ),
        "source_url": None,
    },
    # -- Reference material: textbook RULES are legitimately, widely
    # published in secondary sources; specific copyrighted figures/pages
    # are not reproduced. --
    {
        "source_id": "frost_prechter", "category": "reference_material",
        "name": "Frost & Prechter, Elliott Wave Principle (rule definitions, via legitimate secondary sources)",
        "access_status": "ARCHETYPE_DEFINITION",
        "access_notes": (
            "The book itself is copyrighted; no specific copyrighted figure, page, or "
            "verbatim text is reproduced here. The three hard rules (Wave 2 never "
            "retraces past the origin, Wave 3 never the shortest of 1/3/5, Wave 4 "
            "never overlaps Wave 1) and the named archetype shapes (zigzag, flat "
            "variants, triangle variants, double/triple three, leading/ending "
            "diagonal) are universally and consistently restated across many "
            "independent legitimate secondary sources (StockCharts ChartSchool, "
            "Corporate Finance Institute, Elliott Wave International's own free "
            "pages -- see source_url for the one directly checked) -- this "
            "benchmark tests whether the engine's classification of a constructed "
            "archetype example matches that universally-agreed DEFINITION, not "
            "whether it matches one specific historical chart's book-published count."
        ),
        "source_url": "https://chartschool.stockcharts.com/table-of-contents/market-analysis/elliott-wave-analysis-articles/identifying-elliott-wave-patterns",
    },
    {
        "source_id": "neely", "category": "reference_material",
        "name": "Glenn Neely, Mastering Elliott Wave",
        "access_status": "NO_ACCESS",
        "access_notes": (
            "Copyrighted book with no legitimately accessible free excerpt containing "
            "specific, reproducible chart examples found. The task itself gates this "
            "on licensing ('where licensing permits') -- no license/access was "
            "available in this session, so this category is left empty rather than "
            "approximated from an unverifiable source."
        ),
        "source_url": None,
    },
    {
        "source_id": "public_edu", "category": "reference_material",
        "name": "Public Elliott Wave educational examples (StockCharts ChartSchool, checked directly)",
        "access_status": "ARCHETYPE_DEFINITION",
        "access_notes": (
            "Directly fetched and checked (see source_url): every example on this page "
            "is a generic/idealized schematic diagram (no real symbol, date, or price "
            "level) -- confirmed, not assumed. This is the same 'archetype definition' "
            "status as Frost & Prechter above, for the same underlying reason: public "
            "educational material teaches the SHAPE, it does not publish a specific "
            "historical chart's independently-labeled count."
        ),
        "source_url": "https://chartschool.stockcharts.com/table-of-contents/market-analysis/elliott-wave-analysis-articles/identifying-elliott-wave-patterns",
    },
    # -- Added for Task 9 Improvement, requirement 2 ("Public TradingView
    # ideas"): a genuine, real, publicly-viewable expert count WAS found --
    # but it cannot be turned into a per-chart comparison case, because no
    # legitimate real BTC price feed is available in this environment
    # (Task 8 already confirmed the Schwab "BTC" symbol returns fake
    # ~$48 prices, not real Bitcoin). Documented honestly as found-but-
    # untestable rather than silently dropped or fabricated into a
    # comparison against fake data. --
    {
        "source_id": "tv_rk_chaarts", "category": "community",
        "name": "TradingView Idea: 'A Closer Look at Bitcoin's Elliot Wave Pattern' by RK_Chaarts (BITSTAMP:BTCUSD, Daily)",
        "access_status": "FOUND_NOT_TESTABLE",
        "access_notes": (
            "Publicly viewable without login/subscription -- confirmed by direct fetch. "
            "Contains a genuine, specific expert claim: Daily BTC, primary wave ((4)) "
            "complete, wave ((5)) unfolding, stated invalidation near $76,666 (nearest) "
            "/ below $50,000 (structural). This IS a real independent reference count, "
            "unlike the inaccessible commercial sources above. It is NOT used in any "
            "engine-vs-reference comparison in this benchmark because no legitimate "
            "real BTC price feed is available to run the engine against the same chart "
            "-- doing so would require either a fake price series (misrepresenting the "
            "comparison) or asserting the engine's output on unrelated real data as if "
            "it were 'the BTC comparison' (fabrication). Recorded here so the search for "
            "this source type is documented as genuinely done, not skipped."
        ),
        "source_url": "https://www.tradingview.com/chart/BTCUSD/",
    },
    # -- Internal: the real ES/NQ/SPY/GC/CL data used for Tier 2 (regime/
    # robustness testing) is genuine Schwab-cached market data (verified
    # real in Task 8, distinct from the confirmed-fake BTC/EURUSD feeds),
    # but it is NOT an independent third-party wave-count reference -- no
    # comparison/agreement numbers are computed against it, only
    # robustness properties (determinism, hard-rule compliance) that don't
    # require an external reference count at all. --
    {
        "source_id": "schwab_real_market", "category": "reference_material",
        "name": "Real Schwab-cached OHLCV data (ES, NQ, SPY, GC, CL; 5m/15m/1h/4h/1d) -- reused from Task 8",
        "access_status": "REAL_DATA_NO_REFERENCE_COUNT",
        "access_notes": (
            "Genuine real market data (confirmed in Task 8; not synthetic, not the "
            "confirmed-fake BTC/EURUSD Schwab feeds). Used for objective regime "
            "classification (bull/bear/sideways, high/low-vol, computed directly from "
            "the price series -- see regime_classification.py) and engine ROBUSTNESS "
            "testing (determinism across repeated runs, hard-rule compliance rate). "
            "Deliberately NOT used for wave-count 'agreement' -- no independent, sourced "
            "reference count exists for an arbitrary real-market window (that gap is "
            "exactly what the other reference_sources rows above document); computing "
            "an 'agreement %' against nothing would fabricate a comparison."
        ),
        "source_url": None,
    },
]


def seed():
    init_db()
    with connect() as conn:
        for s in SOURCES:
            conn.execute(
                "INSERT OR REPLACE INTO reference_sources (source_id, category, name, access_status, access_notes, source_url) "
                "VALUES (?,?,?,?,?,?)",
                (s["source_id"], s["category"], s["name"], s["access_status"], s["access_notes"], s["source_url"]),
            )
    print(f"seeded {len(SOURCES)} reference sources")


if __name__ == "__main__":
    seed()
