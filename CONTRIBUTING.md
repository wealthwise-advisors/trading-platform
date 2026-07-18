# Contributing

This is a proprietary, internal project (see [LICENSE](LICENSE)) —
"contributing" here means the internal dev workflow, not an open-source
PR process for outside contributors.

## Before you start

Read [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md), especially the
"Working on the Elliott Wave engine" section if your change touches
`src/analysis/` — that code has an explicit, repeatedly-enforced rule:
**no detector logic, scoring, or DP selection change without objective
evidence** (a failing test, or a measured benchmark regression). This
isn't bureaucracy — every one of the engine's calibration decisions (e.g.
the triangle completion-bonus recalibration in `wave_numbering.py`) is
backed by a specific measurement documented in a comment right next to the
constant it justifies. A new change should meet the same bar.

## Workflow

1. Branch from `master`.
2. Make the change.
3. Run the relevant checks:
   ```bash
   pytest tests/ -v                 # or `elliott validate` for the Elliott suite alone
   ruff check .
   mypy src/analysis --ignore-missing-imports   # informational, see docs/RELEASE_AUDIT.md
   ```
4. If the change touches `src/analysis/`, also run `elliott benchmark`
   and confirm the agreement/reproducibility numbers haven't regressed
   (CI's `benchmark` job gates on `reproducibility == 100%` and
   `agreement >= 20%` — see `.github/workflows/ci.yml`).
5. Open a PR with a description of *why*, not just *what* — same
   convention as existing commit messages in this repo.

## Code style

- `ruff` (config in `pyproject.toml`) is the source of truth for lint;
  `black` for formatting.
- Type hints are encouraged for new code but not enforced repo-wide yet
  (`mypy` currently runs informationally in CI — see
  `docs/RELEASE_AUDIT.md`'s Code Quality Audit for the baseline).
- Don't add abstractions, config flags, or error handling for scenarios
  that can't happen — this codebase favors direct, readable code over
  defensive layering.

## Reporting a bug

Internal: open an issue in this repo (or your team's usual tracker) with
a minimal reproduction. For anything in `src/analysis/`, include the exact
input (OHLC data or pivot list) and which function/endpoint you called —
see `tests/elliott/conftest.py` for the fixture-construction gotchas
(fractal pivot endpoint confirmation) that have caused false "engine bug"
reports before.

## Security issues

Do not open a public issue for a suspected security problem in credential
handling, auth flows, or data exposure. Report it directly to the project
maintainer. See [docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md) for what
was already reviewed as of v1.0.0.
