# Security Audit (Task 10, v1.0.0)

Tooling: `bandit` (static analysis), `pip-audit` (dependency CVEs), manual
review (secrets, `.gitignore` coverage, CORS/debug defaults). Every
finding below was independently verified before being classified real or
false-positive — none is assumed.

## Dependencies

`pip-audit --desc` found **14 known vulnerabilities across 2 packages**:

- **`Pillow` 12.2.0 → 8 CVEs**, all fixed in 12.3.0 (decompression-bomb
  bypasses in PCF/BDF/GD/font parsing, an EPS infinite-loop, a native heap
  OOB write, a native heap corruption path, and a Windows shell-injection
  in `WindowsViewer.get_command()`). Traced to its actual source: pulled
  in transitively by `reportlab` (used for PDF export,
  `api/export/formats.py`), not a direct dependency. **Fixed**: pinned
  `Pillow>=12.3.0` in `pyproject.toml`/`requirements.txt`.
- **`pip` 25.0.1 → 6 CVEs**, fixed in various later versions (entry-point
  path handling, tar/zip extraction path traversal, archive-type
  confusion, an import-timing issue in self-update). This is about the
  `pip` tool itself, not a project dependency — not something to pin in
  `pyproject.toml`. Documented here as a recommendation: run `python -m
  pip install --upgrade pip` before installing this project.

No other dependency in the resolved environment had a known CVE at audit
time.

## Vendored third-party code

`src/data/schwabdev/` (Tyler Bowers' Schwab API client, vendored with
attribution — see [LICENSE](../LICENSE)) was scanned separately since it's
not "our" code to rewrite freely:

- **`bandit` flagged a `requests.post(...)` call without a timeout**
  (`api.py:210`, the OAuth token exchange). Investigating further found
  this is **systemic, not isolated** — all **23** `requests.get/post/put/
  delete` calls in that file lack an explicit timeout. A stalled network
  connection could hang the calling code indefinitely. **Not patched**:
  this is vendored third-party code, the fix touches 23 call sites (not a
  single surgical line), and mass-editing a vendored file risks silent
  drift from upstream in ways that surprise future updates. Documented as
  a real, specific, known limitation with two viable remediation paths
  (recommended for a dedicated follow-up task, not bundled here):
  1. Wrap the module's HTTP calls behind a `requests.Session` configured
     with a default timeout (smallest possible diff, stays close to
     upstream's structure).
  2. Open an upstream PR/issue against
     `tylerebowers/Schwab-API-Python` and pull the fix in on the next sync.

## SQL construction (false positives, verified)

`bandit` flagged 3 f-string-built SQL queries as possible injection
vectors (`validation/dashboard.py:153`, `validation/metrics.py:118,170`).
**Verified false positives**: in all three cases the interpolated value
comes from a hardcoded, fixed-at-definition-time Python list/literal
(e.g. `error_flags = ["false_positive", "false_negative", ...]` — a
constant in the same file), never from request/user input. These are
internal analytics/validation tools (`validation/`) with no external
exposure — traced every call site to confirm this, not assumed from the
pattern alone. No fix needed; `bandit`'s heuristic can't distinguish
"f-string near SQL" from "f-string near SQL with attacker-controlled
content," so this class of finding always needs the manual check done
here.

## Secrets and environment variables

- `config/credentials.yaml` and `config/schwab_tokens.json` are gitignored
  (verified: `git check-ignore -v` confirms both) and were never present
  in git history for this repo's actual tracked files.
- Grepped the full source tree for hardcoded API-key/secret/password-
  shaped string literals: none found.
- `elliott config --show` (new in this release) redacts every field whose
  key name matches a secret-like pattern (`app_key`, `app_secret`,
  `credentials_path`, `token`, `password`, etc.) before printing — spot-
  checked against the real `credentials.yaml` in this environment; a set
  `credentials_path` prints as `***SET***`, an empty `password` prints as
  `(not set)`, neither leaks the real value.
- No environment variable in this codebase carries a secret value directly
  — Schwab credentials are file-based by design (the underlying client
  needs to persist refreshed tokens across restarts, which doesn't fit an
  env-var model); documented in `docs/CONFIGURATION.md`.

## Input validation

- API request bodies are Pydantic-typed (`api/schemas/`) — type coercion
  and required-field validation happen automatically before a handler
  runs.
- `elliott analyze`/`elliott export` validate the input CSV has
  `open`/`high`/`low`/`close` columns before calling the engine, exiting
  with a clean error (not a traceback) otherwise — verified by running
  against a deliberately malformed CSV during this audit.
- `src.config.load_config()` validates required config sections are
  present (`elliott config` surfaces this) rather than silently
  proceeding with a partial config.

## Error exposure

7 call sites across `api/routers/{backtests,data_export,schwab}.py`
return raw exception text (`str(e)`) inside an `HTTPException` detail.
Reviewed every one individually (not as a class): all are scoped,
user-actionable validation messages (e.g. a `FileNotFoundError`'s message
naming which file, or "Not authenticated with Schwab — complete the auth
flow first") — none leaks a stack trace, secret, database connection
string, or filesystem path beyond what the message is already,
legitimately about. Appropriate for a single-operator internal tool where
the API caller and the person who'd read a bug report are the same trust
boundary. **Recommendation**: re-review this specific pattern before any
deployment where the API is exposed to untrusted or multi-tenant callers
— it was not designed for that threat model.

## Unsafe defaults

- **CORS**: none existed before this audit (see
  [API_GUIDE.md](API_GUIDE.md)) — meaning the API had no explicit policy
  at all, which in practice meant no cross-origin browser access was
  possible except through Vite's same-origin dev proxy. **Fixed**: added
  `CORSMiddleware` with an explicit, narrow default (`localhost:5173`,
  `localhost:3000`) rather than a wildcard — a deployer must deliberately
  widen `AUTOTRADER_CORS_ORIGINS` to allow anything else.
- **Debug/reload mode**: confirmed the Dockerfile's production `CMD` does
  **not** pass `--reload` (the only mention of it anywhere is a dev-usage
  example in `api/main.py`'s module docstring). No `debug=True` or
  equivalent found anywhere in `api/`.
- **Non-root container user**: the production `Dockerfile` creates and
  switches to a dedicated `autotrader` user (uid 1000) before the final
  `CMD` — the process never runs as root inside the container.

## Summary

No critical or high-severity finding. One real medium finding (vendored
Pillow CVEs) was fixed directly. One real, systemic finding in vendored
third-party code (missing HTTP timeouts) was documented with a specific
remediation path rather than mass-patched. Three heuristic findings were
investigated and confirmed false positives. Two genuine gaps (no CORS
policy, a no-op availability check) were found and fixed as part of the
API audit. Nothing found rises to a release blocker for the certified
v1.0.0 scope.
