# AutoTrader

A futures/options backtesting platform with bar-by-bar replay and live market
data (Schwab / Rithmic). **v1.0.0.**

**Stack:** FastAPI (`api/`) + React/TypeScript (`web/`) + a Python analysis
core (`src/`). The original Streamlit UI was fully retired on 2026-07-15.

> Live trading (`src/live/`, `src/broker/rithmic_broker.py`) is a
> documented, intentional **stub** — not part of this release. Backtesting
> and replay are the certified v1.0.0 scope. See
> [docs/RELEASE_AUDIT.md](docs/RELEASE_AUDIT.md) for the full readiness
> report.

---

## Quick start

```bash
git clone <repo-url>
cd trading-platform
pip install -e ".[dev]"
```

```bash
# Backend (port 8000)
uvicorn api.main:app --reload --port 8000

# Frontend (port 5173) -- separate terminal
cd web && npm install && npm run dev
```

Open http://localhost:5173. Select **Synthetic Data** and run a backtest —
no credentials needed. Full walkthrough: [docs/QUICKSTART.md](docs/QUICKSTART.md).

### Docker

```bash
docker compose up --build
```

Frontend at http://localhost:8080 (reverse-proxies `/api/*` to the backend
— see [web/nginx.conf](web/nginx.conf)). Details: [docs/INSTALLATION.md](docs/INSTALLATION.md#docker).

---

## Documentation

| Guide | Covers |
|---|---|
| [Installation](docs/INSTALLATION.md) | pip / editable / Docker install, Python version, verifying the install |
| [Quick Start](docs/QUICKSTART.md) | First backtest, first CLI command |
| [Architecture](docs/ARCHITECTURE.md) | How `src/`, `api/`, `web/` fit together |
| [Developer Guide](docs/DEVELOPER_GUIDE.md) | Writing a strategy, running tests |
| [API Guide](docs/API_GUIDE.md) | FastAPI endpoints, OpenAPI docs, auth, CORS |
| [Configuration](docs/CONFIGURATION.md) | `settings.yaml`, `credentials.yaml`, environment variables, Schwab/Rithmic setup |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common errors and fixes |
| [FAQ](docs/FAQ.md) | Short answers to recurring questions |
| [Release Notes](docs/RELEASE_NOTES.md) | What's in v1.0.0 |
| [CHANGELOG](CHANGELOG.md) | Version history |
| [Release Audit](docs/RELEASE_AUDIT.md) | Task 10's full audit: findings, fixes, known limitations, readiness score |
| [Verification Report](docs/VERIFICATION_REPORT.md) | Task 10.1's Gold Certification: every release claim actually executed and re-verified |
| [Security Audit](docs/SECURITY_AUDIT.md) | Dependency CVEs, secret handling, input validation review |
| [CONTRIBUTING](CONTRIBUTING.md) | Dev workflow, code style, PR expectations |

---

## Project structure

```
trading-platform/
├── src/                    # Core engine (no FastAPI/React dependency)
│   ├── analysis/           # Swing/pivot detection, candlestick + chart patterns,
│   │                       #   regime classification
│   ├── backtesting/        # BacktestEngine, ReplayEngine, metrics
│   ├── strategies/         # MA Crossover, RSI, Breakout, RSI Divergence, regime-adaptive
│   ├── broker/              # PaperBroker (live), RithmicBroker (stub)
│   ├── data/                # Schwab, Rithmic, CSV, synthetic data providers
│   └── live/                 # Live trading loop (stub -- not wired to a broker)
├── api/                     # FastAPI service -- routers, schemas, report/export generation
├── web/                     # React + TypeScript + Tailwind + shadcn/ui frontend
├── scripts/                    # CLI utility scripts (data generation, downloads)
├── config/                      # settings.yaml (committed) + credentials.yaml (gitignored)
├── Dockerfile, web/Dockerfile, docker-compose.yml
└── .github/workflows/ci.yml     # lint, typecheck, tests, build, security
```

---

## Tests

```bash
pytest tests/ -v
```

---

## License

Proprietary — All Rights Reserved. See [LICENSE](LICENSE).
