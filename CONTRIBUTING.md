# Contributing

This is a proprietary, internal project (see [LICENSE](LICENSE)) —
"contributing" here means the internal dev workflow, not an open-source
PR process for outside contributors.

## Before you start

Read [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) if your change
touches `src/analysis/`, `src/strategies/`, or `src/backtesting/`.

## Workflow

1. Branch from `master`.
2. Make the change.
3. Run the relevant checks:
   ```bash
   pytest tests/ -v
   ruff check .
   mypy src/analysis --ignore-missing-imports   # informational, see docs/RELEASE.md
   ```
   The `ruff check .` line is also enforced by a pre-commit hook, so it
   runs whether or not you remember to. Enable it once per clone:
   ```bash
   git config core.hooksPath .githooks
   ```
   It runs the same command CI runs, against the same `[tool.ruff]` config
   in `pyproject.toml`, so the two cannot disagree. `git commit --no-verify`
   skips it when you need to.
4. Open a PR with a description of *why*, not just *what* — same
   convention as existing commit messages in this repo.

## Code style

- `ruff` (config in `pyproject.toml`) is the source of truth for lint;
  `black` for formatting.
- Type hints are encouraged for new code but not enforced repo-wide yet
  (`mypy` currently runs informationally in CI — see
  `docs/RELEASE.md`'s Code Quality Audit for the baseline).
- Don't add abstractions, config flags, or error handling for scenarios
  that can't happen — this codebase favors direct, readable code over
  defensive layering.

## Reporting a bug

Internal: open an issue in this repo (or your team's usual tracker) with
a minimal reproduction. For anything in `src/analysis/`, include the exact
input (OHLC data or pivot list) and which function/endpoint you called.

## Security issues

Do not open a public issue for a suspected security problem in credential
handling, auth flows, or data exposure. Report it directly to the project
maintainer. See [docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md) for what
was already reviewed as of v1.0.0.
