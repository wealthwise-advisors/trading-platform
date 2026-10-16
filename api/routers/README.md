<div align="center">

# 🛣 Endpoints

**One module per area of the app. Nothing here computes anything.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Does** | Validate input ➜ call [`src`](../../src) ➜ serialise the answer |
| 🔐 **Guarded** | No sign-in. All but `meta.py` run as the workspace account and refuse cross-origin writes |
| 📐 **Rule** | Business logic belongs in `src`, not in a route |
| 📁 **Path** | `api/routers/` |
| 📦 **Holds** | `9` files · `2,946` lines |


---

## 🔄 How it fits together

```
   HTTP request
        │
        ▼
   ┌──────────────┐  no session   ┌──────────┐
   │  the guard   │ ────────────► │   401    │
   │  (api/auth)  │               └──────────┘
   └──────┬───────┘
          │ user
          ▼
   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
   │  schemas/    │ ─► │  this router │ ─► │    src/      │
   │  validate in │    │  no logic    │    │  the engine  │
   └──────────────┘    └──────┬───────┘    └──────────────┘
                              ▼
                        serializers ──► JSON
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`replay.py`](replay.py) | ▶️ Live replay: create a session, then drive it bar-by-bar over a WebSocket. | 561 |
| [`auth.py`](auth.py) | 🔐 `/me` — the workspace account · `/onboarded` — the introduction flag. | 50 |
| [`backtests.py`](backtests.py) | 📊 Run a backtest, then fetch its trades, equity, patterns and waves. | 390 |
| [`meta.py`](meta.py) | ❤️ Health, version, symbols, timeframes and other reference data. | 254 |
| [`optimize.py`](optimize.py) | 🎯 Sweeps a strategy's own parameter grid and ranks the runs. | 117 |
| [`data_export.py`](data_export.py) | 📤 Raw OHLC export — symbol, range, source ➜ CSV/Excel/PDF/Word. Session hours apply to intraday only. | 89 |
| [`account.py`](account.py) | 👤 The signed-in account: its data, and deleting it. | 103 |
| [`schwab.py`](schwab.py) | 🏦 Schwab OAuth2, a thin wrapper over the provider's own auth methods. | 64 |


---

## 💡 Worth knowing

- ➜ **Routers are guarded as a group**, in [`main.py`](../main.py), not per function — so a new endpoint is protected by default rather than by remembering.
- ➜ **The replay WebSocket is the exception.** A handshake cannot resolve an HTTP dependency, so it checks the cookie itself before `accept()`.


---

<div align="center">

<sub>⬅ <a href="../../README.md">Project README</a> · <a href="..">api</a></sub>

</div>
