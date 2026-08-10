-- Independent Industry Benchmark -- database schema (Task 9, extended by
-- Task 9 Improvement). SQLite, new tables only, outside src/ and api/ --
-- zero production schema/code touched.

CREATE TABLE IF NOT EXISTS reference_sources (
    source_id     TEXT PRIMARY KEY,
    category      TEXT NOT NULL,   -- 'commercial' | 'community' | 'reference_material'
    name          TEXT NOT NULL,
    access_status TEXT NOT NULL,   -- 'NO_ACCESS' | 'RULE_LEVEL_ONLY' | 'ARCHETYPE_DEFINITION' | 'FOUND_NOT_TESTABLE'
    access_notes  TEXT NOT NULL,
    source_url    TEXT
);

CREATE TABLE IF NOT EXISTS benchmark_charts (
    chart_id            TEXT PRIMARY KEY,
    source_id            TEXT NOT NULL REFERENCES reference_sources(source_id),
    -- Task 9 Improvement requirement 2: clearly distinguish real
    -- expert-labelled / educational / synthetic examples. This is the
    -- single field every downstream query segments on.
    case_category         TEXT NOT NULL CHECK (case_category IN
                          ('synthetic_archetype', 'real_market_regime', 'real_reference_found_not_testable')),
    symbol                TEXT NOT NULL,           -- 'SYNTHETIC' for archetypes, real ticker for regime cases
    timeframe             TEXT NOT NULL,            -- 'N/A' for archetypes (scale-invariant by definition)
    date_range             TEXT NOT NULL,
    degree                 TEXT NOT NULL,
    -- Regime metadata -- NULL for synthetic archetypes, objectively
    -- computed (not asserted) for real_market_regime cases -- see
    -- regime_classification.py.
    regime_trend            TEXT,                    -- 'bull' | 'bear' | 'sideways'
    regime_volatility        TEXT,                    -- 'high_vol' | 'low_vol'
    regime_realized_return    REAL,
    regime_realized_vol_pct   REAL,
    expected_structure_type TEXT,                   -- NULL for real_market_regime (no reference count exists)
    expected_primary_count_json TEXT NOT NULL,
    expected_alternate_counts_json TEXT NOT NULL,
    notes                 TEXT NOT NULL,
    price_csv_path         TEXT
);

CREATE TABLE IF NOT EXISTS benchmark_runs (
    run_id                  TEXT PRIMARY KEY,
    chart_id                 TEXT NOT NULL REFERENCES benchmark_charts(chart_id),
    run_index                 INTEGER NOT NULL DEFAULT 0,   -- Task 9 Improvement requirement 6: repeated runs per case
    engine_primary_count_json TEXT NOT NULL,
    engine_alternate_counts_json TEXT NOT NULL,
    engine_structure_type      TEXT,
    confidence                  REAL,
    rule_warnings_json          TEXT NOT NULL,
    recursive_verification_json TEXT NOT NULL,
    rule_violations_json         TEXT NOT NULL DEFAULT '[]',   -- independent hard-rule re-audit, real_market_regime cases
    run_at                       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS benchmark_comparisons (
    comparison_id         TEXT PRIMARY KEY,
    run_id                 TEXT NOT NULL REFERENCES benchmark_runs(run_id),
    -- Task 9 Improvement requirement 3: exact / acceptable-alternate /
    -- partial / disagreement, not just a binary match.
    agreement_level          TEXT NOT NULL CHECK (agreement_level IN
                             ('exact', 'acceptable_alternate', 'partial', 'disagreement', 'not_applicable')),
    primary_agreement       INTEGER NOT NULL,
    alternate_agreement     INTEGER,
    wave_numbering_agreement INTEGER,
    degree_agreement         INTEGER,
    triangle_agreement       INTEGER,
    diagonal_agreement       INTEGER,
    correction_agreement     INTEGER,
    rule_differences_json     TEXT NOT NULL,
    -- Task 9 Improvement requirement 4's exact five-way taxonomy.
    recommendation             TEXT NOT NULL CHECK (recommendation IN
                              ('Engine correct', 'Reference correct', 'Multiple valid interpretations',
                               'Ambiguous market structure', 'Insufficient evidence')),
    recommendation_basis       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rule_comparisons (
    rule_comparison_id  TEXT PRIMARY KEY,
    source_id            TEXT NOT NULL REFERENCES reference_sources(source_id),
    rule_name             TEXT NOT NULL,
    engine_rule            TEXT NOT NULL,
    reference_rule          TEXT NOT NULL,
    agreement                TEXT NOT NULL CHECK (agreement IN ('match', 'engine_stricter', 'reference_stricter', 'not_comparable'))
);

-- Task 9 Improvement requirement 6: reproducibility across repeated runs,
-- keyed per chart so metrics.py can compute a determinism rate without
-- re-deriving it from benchmark_runs' run_index by hand each time.
CREATE TABLE IF NOT EXISTS reproducibility_checks (
    check_id          TEXT PRIMARY KEY,
    chart_id            TEXT NOT NULL REFERENCES benchmark_charts(chart_id),
    n_runs               INTEGER NOT NULL,
    all_identical          INTEGER NOT NULL,   -- 1/0 -- every run byte-identical to the first
    distinct_outputs        INTEGER NOT NULL,   -- how many DISTINCT outputs were observed across n_runs
    checked_at              TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bc_source ON benchmark_charts(source_id);
CREATE INDEX IF NOT EXISTS idx_bc_category ON benchmark_charts(case_category);
CREATE INDEX IF NOT EXISTS idx_runs_chart ON benchmark_runs(chart_id);
CREATE INDEX IF NOT EXISTS idx_comparisons_run ON benchmark_comparisons(run_id);
