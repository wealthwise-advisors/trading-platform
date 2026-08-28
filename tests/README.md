<div align="center">

# 🧪 The Test Suite

**1,720 tests. Four of them decide whether the app is safe to expose.**

![tests](https://img.shields.io/badge/tests-1720-22c55e?style=flat-square) ![files](https://img.shields.io/badge/files-22-0ea5e9?style=flat-square) ![pytest](https://img.shields.io/badge/pytest-3.12-0A9EDC?style=flat-square&logo=pytest&logoColor=white)

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| ▶️ **Run** | `py -3.12 -m pytest tests/ -q` |
| 🔐 **Security suite** | `test_auth` · `test_reset_auth` · `test_oauth_auth` · `test_isolation` |
| 🚨 **Adding a refusal test?** | Add the module to `_SECURITY_SUITES` in [`conftest.py`](conftest.py) — or it passes **without reaching the guard** |
| 🚨 **Adding a route?** | Two guards fail on purpose: the OpenAPI sweep and an exact route count |
| 📁 **Path** | `tests/` |
| 📦 **Holds** | `22` files · `7,244` lines · `2` subfolders |


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`test_auth.py`](test_auth.py) | 🔐 Every route refuses an anonymous caller. Sessions die on logout. A new account never gets the broker. | 497 |
| [`test_oauth_auth.py`](test_oauth_auth.py) | 🌐 Four providers. Only a **verified** address may match an account; a disabled one is refused, never re-provisioned. | 684 |
| [`test_reset_auth.py`](test_reset_auth.py) | 🔑 Recovery leaks nothing — not by body, status or timing. Tokens single-use, expiring, purpose-scoped. | 678 |
| [`test_isolation.py`](test_isolation.py) | 🚧 One user cannot reach another's data. Routes swept from the app's own OpenAPI schema. | 392 |
| [`conftest.py`](conftest.py) | ⚙️ Shared setup. `_SECURITY_SUITES` exempts the four above from the signed-in override. | 91 |
| [`test_indicator_correctness.py`](test_indicator_correctness.py) | 📊 Bar construction: boundaries **and** OHLC, every timeframe. | 1,069 |
| [`test_multi_replay.py`](test_multi_replay.py) | 🕐 The multi-timeframe replay clock. | 663 |
| [`test_replay_follow_live.py`](test_replay_follow_live.py) | 📡 Following the live market over the WebSocket. | 477 |
| [`test_swing_zigzag_regression.py`](test_swing_zigzag_regression.py) | 📐 Regression baseline for swing and zigzag labelling. | 436 |
| [`test_replay_extend.py`](test_replay_extend.py) | ➕ Growing a replay past the snapshot it loaded. | 398 |
| [`test_follow_live_matrix.py`](test_follow_live_matrix.py) | 🔢 Every timeframe, offset and date. | 321 |
| [`test_api_provider_errors.py`](test_api_provider_errors.py) | ⚠️ An unservable symbol is a **400**, not a 500. | 266 |
| [`test_reference_platform_parity.py`](test_reference_platform_parity.py) | 🎯 Parity against the reference platform, pinned to real printed bars. | 201 |
| [`test_store_persistence.py`](test_store_persistence.py) | 💾 Results survive a restart. | 258 |
| [`test_vwap_bands.py`](test_vwap_bands.py) | 📏 VWAP and its deviation bands. | 175 |
| [`test_symbol_universe.py`](test_symbol_universe.py) | 🔤 The symbol list stays coherent. | 117 |
| [`test_provider_timeframes.py`](test_provider_timeframes.py) | ⏱ Each provider serves what it claims. | 83 |
| [`test_schwab_redirect_parsing.py`](test_schwab_redirect_parsing.py) | 🏦 Schwab's redirect URL, parsed exactly. | 158 |
| [`test_replay_seek.py`](test_replay_seek.py) | ⏩ Seeking within a replay. | 66 |
| [`test_replay_session_message.py`](test_replay_session_message.py) | 💬 Session messages over the socket. | 120 |
| [`test_engine.py`](test_engine.py) | ▶️ Engine smoke tests on synthetic data. | 57 |
| [`_isolation_helpers.py`](_isolation_helpers.py) | A minimal result object. Underscore-prefixed so pytest ignores it. | 37 |


---

## 🗃 Subfolders

| Folder | ➜ What lives there |
|:--|:--|
| [`fixtures/`](fixtures) | 📎 Pinned data the tests read |
| [`test_elliott_wave/`](test_elliott_wave) | 🌊 The wave engine's own suite |


---

<div align="center">

<sub>⬅ <a href="../README.md">Project README</a></sub>

</div>
