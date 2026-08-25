# Release Notes — v1.0.0

**Certified scope**: backtesting engine, bar-by-bar replay, the Elliott
Wave analysis engine, the FastAPI + React platform around them, and the
tooling to run/validate/package/deploy all of the above.

**Not in this release**: live order placement (`src/live/`,
`src/broker/rithmic_broker.py` remain an intentional stub — see "Known
limitations" in [RELEASE_AUDIT.md](RELEASE_AUDIT.md)).

> [!IMPORTANT]
> **Historical record — accurate for 2026-07-18, not for today.** The Elliott
> Wave engine described below was removed in full and rebuilt from scratch in
> `c74fcf1` (2026-08-10), so its test count, its 80% coverage figure and its
> benchmark no longer describe anything in this repository. The current engine
> lives in [`src/analysis/elliott_wave/`](../src/analysis/elliott_wave) and is
> documented in [ELLIOTT_WAVE_IMPLEMENTATION.md](ELLIOTT_WAVE_IMPLEMENTATION.md)
> and [ELLIOTT_WAVE_RULES.md](ELLIOTT_WAVE_RULES.md). Everything outside the
> Elliott Wave section — the backtesting engine, replay, the platform — still
> stands.

## Highlights

### Elliott Wave engine

- Full pattern coverage: impulses, all four correction variants (zigzag,
  regular/expanded/running flat), contracting/expanding triangles,
  double/triple-three complex corrections, leading/ending diagonals.
- Hard-rule enforcement (Wave 2/3/4 rules) with soft Fibonacci confidence
  scoring layered on top, never as a gate.
- Recursive structural verification and unified cross-pattern
  classification (impulse/correction/triangle/complex-correction/diagonal
  scored together, not in separate silos).
- 56-test automated regression suite, 80% coverage on `src/analysis/`.
- Expert chart-validation framework (369 real chart reviews across 5
  markets × 5 timeframes).
- Independent industry benchmark: 473 cases, 95% confidence intervals,
  Cohen's Kappa, a documented five-way disagreement taxonomy, and a 100%
  reproducibility result across repeated runs. The full report lived at
  `benchmark/TASK9_IMPROVEMENT_REPORT.md`; it was removed in `c74fcf1` together
  with the implementation it measured, and is recoverable from that commit's
  parent.

### Platform

- FastAPI backend + React/TypeScript frontend (the original Streamlit UI
  was fully retired 2026-07-15).
- `elliott` production CLI: `analyze`, `benchmark`, `validate`, `export`,
  `version`, `config`.
- Docker deployment (API + nginx-served frontend, reverse-proxied).
- GitHub Actions CI: lint, type-check, unit tests, regression suite,
  benchmark regression gate, security scan, package build.
- `pyproject.toml` packaging with a corrected, audited dependency list.

## Fixed in this release (Task 10 audit)

- `requirements.txt` was missing `fastapi`, `uvicorn`, `pydantic`,
  `openpyxl`, `reportlab`, and `python-docx` despite all six being
  actively used — a fresh install could not have run the API or served
  its export endpoints.
- `streamlit` and `scipy` were listed as dependencies with zero remaining
  imports anywhere in the codebase — removed.
- `Pillow` pinned to `>=12.3.0` — the transitively-installed 12.2.0
  carried 8 known CVEs (pip-audit).
- `GET /api/data-sources` reported Schwab as always available regardless
  of whether it was actually configured (a no-op `try` block) — now
  performs the same real check the other three data sources already did.
- No CORS policy existed — added, configurable via
  `AUTOTRADER_CORS_ORIGINS`, needed for any deployment topology where the
  frontend isn't reverse-proxied to the same origin as the API.
- No `/api/version` endpoint existed — added.
- 24 unused imports removed (outside the protected `src/analysis/`
  Elliott engine and the vendored `src/data/schwabdev/` client, neither of
  which was touched — see below).

## Explicitly not changed

Per this task's instructions: no Elliott Wave detection logic, scoring,
recursive verification, or DP candidate selection was modified. Findings
inside `src/analysis/` (7 unused imports, 12 ambiguous single-letter
variable names, 2 lambda-assignments, 2 unused locals, 36 mypy type
errors, 1 dead-code loop in a `__main__` demo block) are documented in
[RELEASE_AUDIT.md](RELEASE_AUDIT.md) rather than fixed. The vendored
`src/data/schwabdev/` Schwab API client (third-party, kept close to
upstream) was likewise left as-is beyond documentation, including a
systemic missing-timeout pattern across 23 `requests.*` calls flagged by
`bandit`.

## Versioning

This project follows [Semantic Versioning](https://semver.org/). v1.0.0 is
the first version with a formal release process; see
[CHANGELOG.md](../CHANGELOG.md) for what preceded it.
