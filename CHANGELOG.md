# Changelog

Format loosely follows [Keep a Changelog](https://keepachangelog.com/);
versioning follows [Semantic Versioning](https://semver.org/). Entries
before v1.0.0 summarize development milestones rather than individual
commits — this is the first release with a formal changelog process.

## [Unreleased]

### Removed

- The entire Elliott Wave analysis engine (`src/analysis/elliott_wave.py`,
  `wave_analysis.py`, `wave_numbering.py`, `diagonal_waves.py`,
  `recursive_structure.py`, `structure_classification.py`,
  `complex_corrections.py`, `corrective_waves.py`, `fibonacci.py`),
  its FastAPI endpoint (`api/routers/elliott_wave.py`, `/api/backtests/{id}/elliott-wave`),
  its static-report chart layout (`api/report/wave_layout.py`), its React
  UI (`ElliottWavePanel.tsx`, `ElliottWaveChart.tsx`, `WaveNotesPanel.tsx`,
  the "Elliott Wave" results tab), its independent benchmark (`benchmark/`),
  its expert chart-validation framework (`validation/`), the `elliott`
  production CLI (`cli/`), and its regression suite (`tests/elliott/`).
- `swing_identification.py` is retained (also used by
  `src/backtesting/trade_quality.py`); its docstrings/comments were
  reworded to drop Elliott-specific phrasing.
- The from-scratch replacement Elliott Wave engine that had been built
  after the above removal is itself now removed, in full: the six-layer
  package (`src/analysis/elliott_wave/` — `models.py`, `hierarchy.py`,
  `impulse.py`, `correction.py`, `advanced.py`, `scoring.py`,
  `pipeline.py`), its API surface (`GET /api/backtests/{id}/elliott-wave`,
  `api/serializers.py::elliott_wave_to_records()`, the `show_elliott_wave`
  / `ew_beam_width` / `ew_max_depth` report query parameters and the
  matching `generate_html_report()` / `_candlestick_chart()` parameters,
  `api/report/report.py::_add_elliott_wave_overlay()`), its React UI (the
  `🌊 Elliott Wave` results tab, `ElliottWaveChart.tsx`, `api.getElliottWave()`,
  and the `ElliottWaveResponse` / `ElliottWaveStructure` / `ScoringEvidence` /
  `TargetZoneRecord` TypeScript interfaces), its 196-test suite
  (`tests/test_elliott_wave_*.py`, 7 files), and its design documentation
  (`docs/ELLIOTT_WAVE_ARCHITECTURE.md`, `docs/ELLIOTT_WAVE_SRS.md`,
  `docs/ELLIOTT_WAVE_V1_RELEASE.md`). No replacement was built.
- Dead `COPY cli/ benchmark/ validation/` lines dropped from the
  `Dockerfile` — all three directories were Elliott-only and had already
  been deleted, so the image build referenced paths that no longer existed.
- `src/analysis/swing_identification.py`, `src/analysis/zigzag.py`, the
  Swing (10-Leg) / 3-Leg Deviation overlay, and
  `tests/test_swing_zigzag_regression.py` are all untouched by this
  removal — the Elliott engine consumed `identify_swings()`/`atr()`, it
  never owned them.

## [1.0.0] — Version 1.0 Gold

Full production release audit: repository/code-quality audit, packaging
(`pyproject.toml`, corrected dependency list), FastAPI audit (added
`/api/version`, fixed a Schwab-availability bug, added CORS), the
`elliott` production CLI, Docker deployment assets, GitHub Actions CI/CD,
a full documentation set, a performance audit, and a security audit. Full
detail: [docs/RELEASE_AUDIT.md](docs/RELEASE_AUDIT.md).

### Added
- `pyproject.toml`, corrected `requirements.txt`, `.env.example`
- `elliott` CLI (`cli/`): analyze, benchmark, validate, export, version, config
- `Dockerfile`, `web/Dockerfile`, `web/nginx.conf`, `docker-compose.yml`, `.dockerignore`
- `.github/workflows/ci.yml`
- `GET /api/version`; CORS middleware (`AUTOTRADER_CORS_ORIGINS`)
- Full `docs/` set, `CHANGELOG.md`, `LICENSE`, `CONTRIBUTING.md`

### Fixed
- `requirements.txt` missing `fastapi`/`uvicorn`/`pydantic`/`openpyxl`/`reportlab`/`python-docx`
- Stale `streamlit`/`scipy` dependencies removed (zero remaining imports)
- `Pillow` pinned to `>=12.3.0` (8 known CVEs in the transitively-installed 12.2.0)
- `/api/data-sources` unconditionally reported Schwab as available (no-op check)
- 24 unused imports removed (outside the Elliott engine and vendored Schwab client)

## Elliott Wave engine development (pre-1.0.0)

- **Independent industry benchmark, gold-standard expansion** — grew the
  benchmark from 13 to 473 cases (104 synthetic archetype variants + 369
  real-market robustness cases across 5 symbols × 5 timeframes), a
  five-way disagreement taxonomy, 95% confidence intervals, Cohen's Kappa,
  and a 100%-reproducible determinism harness.
- **Independent industry benchmark** — first version: 13 textbook
  archetype cases, rule-level comparison against an open-source
  TradingView Pine script, an honest access-status audit of every
  requested reference source (MotiveWave/ELWAVE/ElliottWaveForecast/Neely
  confirmed inaccessible, documented rather than faked).
- **Expert chart validation framework** — SQLite-backed review pipeline,
  369 real charts (ES/NQ/SPY/GC/CL × 5m/15m/1h/4h/1d), scorecards, exports,
  dashboards.
- **Production regression & validation suite** — 56 pytest tests across
  `tests/elliott/`: canonical cases per pattern type, prior-bugfix
  regressions, performance bounds, determinism, API regression.
- **Diagonal detection — production-quality pass** — forward-context
  leading/ending position classification replacing a heuristic measured at
  2.5% real-world agreement.
- **Leading & ending diagonal detection**.
- **Triangle & complex correction integration — calibration pass** —
  evidence-driven recalibration of corrective-completion scoring bonuses
  (triangle bonus lowered from 0.9 to 0.55 based on measured win-rate
  across 15 dataset/timeframe combinations).
- **Triangle & complex correction detection** — `detect_triangle`,
  `find_combinations` (WXY/WXYXZ), `find_triangle_candidates`.
- **Recursive structural subdivision engine — production-quality pass** —
  LRU cache tuning based on measured working-set size; recursion into all
  qualifying sub-windows, not just the largest.
- **Recursive structural subdivision engine** — generic, detector-agnostic
  recursive verification with explicit UNKNOWN on any miss.
- **Unified structure classification** — `classify_structure_detailed`
  scores impulse/correction/triangle/complex-correction/diagonal
  hypotheses together per swing position, replacing separate per-pattern
  silos.
- **Core Elliott Wave engine** — swing identification, impulse validation
  (three hard rules), Fibonacci confidence scoring, zigzag/flat correction
  classification.

## Platform (pre-1.0.0, undated)

- FastAPI + React/TypeScript platform built out (`api/`, `web/`) alongside
  the original Streamlit UI.
- Streamlit UI fully retired (2026-07-15); FastAPI + React became the sole
  application. `ui/report.py` and `ui/components/charts.py` survived the
  migration (no Streamlit dependency) as `api/report/report.py` and
  `api/report/charts.py`.
- Backtesting engine, replay engine, paper broker, four built-in
  strategies (MA Crossover, RSI Mean Reversion, Breakout, RSI Divergence).
- Schwab OAuth2 data provider; Rithmic historical/live data provider
  (stub broker, not wired to live trading).
