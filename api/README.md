# 🔌 `api`

**The FastAPI service the dashboard talks to.**

A thin layer. The API validates a request, calls into [`src/`](../src), and
serialises the answer — it holds no trading logic of its own, which is what keeps the
engine testable without a server.

| Package | Role |
|---|---|
| [`routers/`](routers) | REST endpoints, the replay WebSocket, sign-in and OAuth |
| [`schemas/`](schemas) | Pydantic request and response models |
| [`report/`](report) | Server-side chart and report rendering |
| [`export/`](export) | CSV · XLSX · PDF · DOCX writers |

### 🔐 Accounts

Five modules, kept apart from the trading code because they answer a different
question — *who is asking* rather than *what is the answer*.

| File | Role |
|---|---|
| [`auth.py`](auth.py) | argon2id hashing, session cookies, the route guard, and the three rate limiters |
| [`oauth.py`](oauth.py) | The provider table — Google · LinkedIn · GitHub · Twitter — plus PKCE, token exchange and profile normalisation |
| [`verification.py`](verification.py) | Email via Resend: confirmation links, password resets, username reminders |
| [`captcha.py`](captcha.py) | Cloudflare Turnstile. Fails **closed** once configured |

➜ **Dormant is a supported state.** With no credentials each of these reports
itself unconfigured and the feature stays shut — nothing pretends to have sent
a message it did not send, and no button claims to work when it cannot.

➜ **An account grants the analysis app and not the broker.** There is one
Schwab connection and it is the operator's own, so `users.is_owner` defaults to
`0` and no route can set it.

Interactive documentation is served at `/docs` while running.

### Files in this directory

| File | Purpose | Lines |
|---|---|---:|
| [`serializers.py`](serializers.py) | Plain functions converting BacktestResults / pandas objects into the JSON- ready shapes defined in… | 345 |
| [`strategy_registry.py`](strategy_registry.py) | Strategy metadata + construction, centralized here so the frontend can render a generic parameter form… | 98 |
| [`main.py`](main.py) | FastAPI backend for the AutoTrader dashboard. | 112 |
| [`deps.py`](deps.py) | Shared FastAPI dependencies — config loading, contract specs. | 55 |
| [`replay_store.py`](replay_store.py) | In-memory store for live-replay sessions, mirroring api/store.py's design (single-process, dev-appropriate). | 48 |
| [`auth.py`](auth.py) | Password hashing, sessions, the guard every protected route depends on, and the login / signup / recovery throttles. | 439 |
| [`oauth.py`](oauth.py) | The four sign-in providers, their differences, and the exchange that turns a code into a profile. | 403 |
| [`verification.py`](verification.py) | Resend delivery for confirmation, reset and username-reminder mail. | 347 |
| [`captcha.py`](captcha.py) | Turnstile verification, dormant without keys, failing closed with them. | 127 |
| [`store.py`](store.py) | Backtest result cache, keyed by **(user_id, backtest_id)** — a cache hit returns before any query runs, so the owner has to be part of the key. | 132 |
| [`requirements-api.txt`](requirements-api.txt) | Python packages the API service needs, pinned for the container build. | 5 |

### Subdirectories

| Directory | Files |
|---|---:|
| [`export/`](export) | 3 |
| [`report/`](report) | 3 |
| [`routers/`](routers) | 9 |
| [`schemas/`](schemas) | 6 |

---

<sub>[⬅ Back to the project README](../README.md)</sub>
