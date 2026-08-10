# Changelog

Format loosely follows [Keep a Changelog](https://keepachangelog.com/);
versioning follows [Semantic Versioning](https://semver.org/). Entries
before v1.0.0 summarize development milestones rather than individual
commits — this is the first release with a formal changelog process.

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
