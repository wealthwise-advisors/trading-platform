<div align="center">

# 🛣 Endpoints

**One module per area of the app. Nothing here computes anything.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Does** | Validate input ➜ call [`src/`](../../src) ➜ serialise the answer |
| 🔐 **Guarded** | All of these except `auth.py`, `oauth.py` and `meta.py` |
| 📐 **Rule** | Business logic belongs in `src/`, not in a route |
| 📦 **Holds** | `8` files · `2,275` lines |


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`replay.py`](replay.py) | ▶️ Live replay: create a session, then drive it bar-by-bar over a WebSocket. | 561 |
| [`auth.py`](auth.py) | 🔐 Sign in · register · sign out · password reset · username reminder · email verification. | 524 |
| [`oauth.py`](oauth.py) | 🌐 `/providers`, `/{name}/start`, `/{name}/callback` — the whole redirect dance. | 324 |
| [`backtests.py`](backtests.py) | 📊 Run a backtest, then fetch its trades, equity, patterns and waves. | 347 |
| [`meta.py`](meta.py) | ❤️ Health, version, symbols, timeframes and other reference data. | 254 |
| [`optimize.py`](optimize.py) | 🎯 Sweeps a strategy's own parameter grid and ranks the runs. | 117 |
| [`data_export.py`](data_export.py) | 📤 Raw OHLC export — symbol, range, source ➜ CSV/Excel/PDF/Word. | 84 |
| [`schwab.py`](schwab.py) | 🏦 Schwab OAuth2, a thin wrapper over the provider's own auth methods. | 64 |


---

## 💡 Worth knowing

- ➜ **Routers are guarded as a group**, in [`api/main.py`](../main.py), not per function — so a new endpoint is protected by default rather than by remembering.
- ➜ **The replay WebSocket is the exception.** A handshake cannot resolve an HTTP dependency, so it checks the cookie itself before `accept()`.


---

<div align="center">

<sub>⬅ <a href="../../README.md">Project README</a> · <a href="..">api/</a></sub>

</div>
