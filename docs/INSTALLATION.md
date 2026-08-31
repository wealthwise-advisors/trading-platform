# Installation

## Requirements

- Python **3.12** (use the `py -3.12` launcher on Windows — `python` or `py -3` may resolve to a different version)
- Node 18+ (only if you're running the React frontend outside Docker)
- Git

## Option 1 — editable install (recommended for development)

```bash
git clone <repo-url>
cd trading-platform
pip install -e ".[dev]"
```

This installs the core runtime dependencies plus dev tooling (pytest,
ruff, mypy, vulture, bandit, pip-audit, black).

For live/real Rithmic data, add the `live` extra:

```bash
pip install -e ".[live,dev]"
```

## Option 2 — plain pip install (no dev tooling)

```bash
pip install -r requirements.txt
pip install -e . --no-deps
```

## Verifying the install

```bash
pytest tests/ -v
```

Exits non-zero if any test fails — safe to use as an install smoke test in
a script.

## Building a wheel

```bash
pip install build
python -m build --wheel
pip install dist/autotrader-1.0.0-py3-none-any.whl
```

The v1.0.0 wheel is ~248 KB. This was verified end-to-end during the Task
10 release audit: built and installed into a clean virtual environment
with no other files present.

## Docker

```bash
docker compose up --build
```

Starts two services:

| Service | Port | What it is |
|---|---|---|
| `web` | 8080 | React frontend (nginx), reverse-proxies `/api/*` to `api` |
| `api` | (internal only by default) | FastAPI backend |

Open http://localhost:8080. To reach the API directly (e.g. for a Postman
smoke test), uncomment the `ports:` mapping under `api` in
`docker-compose.yml`.

> **Honesty note**: the Dockerfiles and compose file were hand-reviewed and
> match the same dependency list and startup command verified to work
> outside Docker (see above), but a Docker daemon was not available in the
> environment this release audit ran in, so `docker compose up --build`
> itself has **not** been executed end-to-end. Run it once before relying
> on it in production and report back if anything doesn't match this doc
> — see [RELEASE.md](RELEASE.md#audit) for the full list of what was
> and wasn't independently verified.

### Configuration in Docker

`config/` is mounted read-only into the `api` container. Copy
`config/credentials.yaml.example` to `config/credentials.yaml` on the host
*before* `docker compose up` if you need Schwab or Rithmic — without it,
synthetic data, backtesting, and replay all work with zero external
credentials.

## Uninstall

```bash
pip uninstall autotrader
```
