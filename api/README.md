<div align="center">

# 🔌 The API Layer

**Every HTTP route, and the accounts system that guards them.**

![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?style=flat-square&logo=fastapi&logoColor=white) ![auth](https://img.shields.io/badge/auth-argon2id-7c6cf5?style=flat-square) ![routes](https://img.shields.io/badge/routes-38-0ea5e9?style=flat-square)

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Does** | Turns HTTP requests into calls on [`src/`](../src), and answers **who is asking** |
| 🔐 **Guards** | Every route except sign-in, OAuth and health needs a session |
| 🧩 **Owns nothing** | No strategy or indicator logic lives here — it is a thin consumer |
| 📦 **Holds** | `11` files · `2,143` lines · `4` subfolders |


---

## 🔄 How it fits together

```
   browser
      │
      ▼
   ┌──────────────┐   session cookie    ┌──────────────┐
   │  routers/    │ ──────────────────► │   auth.py    │  argon2id · sessions
   │  the routes  │ ◄────────────────── │   the guard  │  throttles · the guard
   └──────┬───────┘      user or 401    └──────────────┘
          │
          ▼
   ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
   │  schemas/    │      │    src/      │      │     db/      │
   │  in and out  │      │  the engine  │      │  persistence │
   └──────────────┘      └──────────────┘      └──────────────┘
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`auth.py`](auth.py) | 🔐 argon2id hashing, session cookies, the route guard, and the three rate limiters. | 439 |
| [`oauth.py`](oauth.py) | 🌐 The four providers — Google · LinkedIn · GitHub · X — PKCE, token exchange, profile normalising. | 403 |
| [`verification.py`](verification.py) | ✉️ Resend delivery: confirmation, password reset, username reminder. | 347 |
| [`captcha.py`](captcha.py) | 🛡 Cloudflare Turnstile. Dormant without keys, and fails **closed** with them. | 127 |
| [`serializers.py`](serializers.py) | Turns engine objects into the JSON the UI expects. | 345 |
| [`main.py`](main.py) | The app object: routers, CORS, logging, and the unhandled-error handler. | 144 |
| [`store.py`](store.py) | Result cache keyed by **(user_id, backtest_id)** — a hit returns before any query, so the owner must be in the key. | 132 |
| [`strategy_registry.py`](strategy_registry.py) | The list of strategies and their parameter grids, shared by the runner and the optimiser. | 98 |
| [`replay_store.py`](replay_store.py) | Live replay sessions held in memory. | 48 |
| [`deps.py`](deps.py) | Shared FastAPI dependencies. | 55 |
| [`requirements-api.txt`](requirements-api.txt) | Python packages the API image installs. | 5 |


---

## 🗃 Subfolders

| Folder | ➜ What lives there |
|:--|:--|
| [`export/`](export) | 📤 CSV · XLSX · PDF · DOCX writers |
| [`report/`](report) | 📈 Server-side chart and report rendering |
| [`routers/`](routers) | 🛣 The endpoints themselves, one module per area |
| [`schemas/`](schemas) | 📋 Pydantic request and response models |


---

## 💡 Worth knowing

- ➜ **Dormant is a supported state.** With no credentials, each integration reports itself unconfigured and stays shut — nothing pretends to have sent mail it did not send.
- ➜ **An account grants the app, never the broker.** `users.is_owner` defaults to `0`, `create_user` has no parameter for it, and no route can set it.
- ➜ **Adding a route?** Two tests will fail on purpose — the guard sweep and an exact route count. Raise them deliberately.


---

<div align="center">

<sub>⬅ <a href="../README.md">Project README</a></sub>

</div>
