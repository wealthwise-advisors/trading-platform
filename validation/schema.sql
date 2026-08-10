-- Expert Chart Validation Framework -- database schema (Task 8).
-- SQLite: single portable file, no server process required. New tables
-- only, entirely outside src/ and api/ -- zero production schema/code
-- touched.

CREATE TABLE IF NOT EXISTS charts (
    chart_id      TEXT PRIMARY KEY,
    market        TEXT NOT NULL,             -- ES | NQ | SPY | BTC | EURUSD | GC | CL
    timeframe     TEXT NOT NULL,              -- 5m | 15m | 1h | 4h | 1d
    start_date    TEXT NOT NULL,
    end_date      TEXT NOT NULL,
    bar_count     INTEGER NOT NULL,
    data_source   TEXT NOT NULL,              -- 'schwab_real' | 'unavailable'
    price_csv_path TEXT,                      -- cached raw OHLCV, for chart re-render
    fetched_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analyses (
    analysis_id                TEXT PRIMARY KEY,
    chart_id                   TEXT NOT NULL REFERENCES charts(chart_id),
    degree                     TEXT NOT NULL,   -- 'primary' | 'minor'
    n_swings                   INTEGER,
    bias                       TEXT,
    cycle_position              TEXT,
    primary_count_json         TEXT NOT NULL,   -- serialized wave_sequence (wave, price, bar, kind)
    alternate_counts_json      TEXT NOT NULL,   -- serialized alternates (text list from _select_best_counts)
    impulse_quality            REAL,            -- avg fraction of legs with sub=1 (fib+pattern) across selected impulses
    corrective_quality         REAL,            -- avg CorrectiveCandidate.quality across selected combos
    triangle_quality           REAL,            -- avg CorrectiveCandidate.quality across selected triangles
    diagonal_quality           REAL,            -- avg (0.7*quality + 0.3*subdivision_bonus) across selected diagonals
    confidence                 REAL,            -- avg classify_structure_detailed().winner_confidence at each selected candidate's origin
    recursive_verification_json TEXT,           -- per selected candidate: verified/confidence/depth_reached/resolved_type
    rule_violations_json       TEXT NOT NULL,   -- independent re-check against WAVE*_RETRACE/EXTENSION gates -- expected empty
    warnings_json               TEXT NOT NULL,   -- wave_analysis.WaveAnalysis.warnings, verbatim
    notes_json                  TEXT NOT NULL,   -- wave_analysis.WaveAnalysis.notes, verbatim
    analyzed_at                 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    review_id         TEXT PRIMARY KEY,
    analysis_id        TEXT NOT NULL REFERENCES analyses(analysis_id),
    reviewer           TEXT NOT NULL,
    verdict             TEXT NOT NULL CHECK (verdict IN ('Correct', 'Acceptable Alternate', 'Incorrect', 'Ambiguous')),
    false_positive      INTEGER NOT NULL DEFAULT 0,   -- engine labeled a structure that isn't there
    false_negative      INTEGER NOT NULL DEFAULT 0,   -- engine missed a structure that IS there
    mis_numbering       INTEGER NOT NULL DEFAULT 0,   -- structure right, wave numbers wrong
    wrong_degree        INTEGER NOT NULL DEFAULT 0,
    missed_triangle     INTEGER NOT NULL DEFAULT 0,
    missed_diagonal     INTEGER NOT NULL DEFAULT 0,
    wrong_correction    INTEGER NOT NULL DEFAULT 0,   -- corrective TYPE wrong (e.g. called flat, actually zigzag)
    notes               TEXT,
    reviewed_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analyses_chart ON analyses(chart_id);
CREATE INDEX IF NOT EXISTS idx_reviews_analysis ON reviews(analysis_id);
CREATE INDEX IF NOT EXISTS idx_charts_market_tf ON charts(market, timeframe);
