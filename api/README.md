# 🔌 `api`

**The FastAPI service the dashboard talks to.**

A thin layer. The API validates a request, calls into [`src/`](../src), and
serialises the answer — it holds no trading logic of its own, which is what keeps the
engine testable without a server.

| Package | Role |
|---|---|
| [`routers/`](routers) | REST endpoints and the replay WebSocket |
| [`schemas/`](schemas) | Pydantic request and response models |
| [`report/`](report) | Server-side chart and report rendering |
| [`export/`](export) | CSV · XLSX · PDF · DOCX writers |

Interactive documentation is served at `/docs` while running.

### Files in this directory

| File | Purpose | Lines |
|---|---|---:|
| [`serializers.py`](serializers.py) | Plain functions converting BacktestResults / pandas objects into the JSON- ready shapes defined in… | 345 |
| [`strategy_registry.py`](strategy_registry.py) | Strategy metadata + construction, centralized here so the frontend can render a generic parameter form… | 98 |
| [`main.py`](main.py) | FastAPI backend for the AutoTrader dashboard. | 83 |
| [`deps.py`](deps.py) | Shared FastAPI dependencies — config loading, contract specs. | 48 |
| [`replay_store.py`](replay_store.py) | In-memory store for live-replay sessions, mirroring api/store.py's design (single-process, dev-appropriate). | 48 |
| [`store.py`](store.py) | In-memory backtest result cache, keyed by backtest_id. | 34 |
| [`requirements-api.txt`](requirements-api.txt) | Python packages the API service needs, pinned for the container build. | 5 |

### Subdirectories

| Directory | Files |
|---|---:|
| [`export/`](export) | 3 |
| [`report/`](report) | 3 |
| [`routers/`](routers) | 7 |
| [`schemas/`](schemas) | 6 |

---

<sub>[⬅ Back to the project README](../README.md)</sub>
