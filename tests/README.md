<div align="center">

# 🧪 The Test Suite

**2,227 tests. Four of them decide whether the app is safe to expose.**

![tests](https://img.shields.io/badge/tests-2227-22c55e?style=flat-square) ![files](https://img.shields.io/badge/files-33-0ea5e9?style=flat-square) ![pytest](https://img.shields.io/badge/pytest-3.12-0A9EDC?style=flat-square&logo=pytest&logoColor=white)

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| ▶️ **Run** | `py -3.12 -m pytest tests/ -q` |
| 🔐 **Workspace suites** | `test_isolation` · `test_account_data` · `test_live_sessions` · `test_backup_restore` · `test_account_deletion` |
| 🚨 **Need the real workspace account?** | Add the module to `_REAL_WORKSPACE_SUITES` in [`conftest.py`](conftest.py) — or the stand-in answers instead |
| 🚨 **Adding a route?** | An exact route count fails on purpose — raise it deliberately |
| 📁 **Path** | `tests/` |
| 📦 **Holds** | `33` files · `10,445` lines · `2` subfolders |


---

## 🔄 How it fits together

```
   ┌── unit ──────────────► a mechanism broke
   ├── behavioural matrix ► a rule about what you are shown broke
   └── confirmed baseline ► something already verified has changed
                                   │
   ╳ never "update the numbers to match" ──┘

   conftest.py: _SECURITY_SUITES
        │
        └── a refusal test NOT listed there runs with require_user
            overridden, and passes without ever reaching the guard.
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`test_isolation.py`](test_isolation.py) | 🚧 One account's rows are invisible to another at the data layer. Every result route swept from the app's own OpenAPI schema. | 337 |
| [`conftest.py`](conftest.py) | ⚙️ Shared setup. `_REAL_WORKSPACE_SUITES` runs the workspace suites against the real account, not the stand-in. | 87 |
| [`test_indicator_correctness.py`](test_indicator_correctness.py) | 📊 Bar construction: boundaries **and** OHLC, every intraday timeframe. | 1,188 |
| [`test_multi_replay.py`](test_multi_replay.py) | 🕐 The multi-timeframe replay clock. | 663 |
| [`test_replay_follow_live.py`](test_replay_follow_live.py) | 📡 Following the live market over the WebSocket. | 477 |
| [`test_swing_zigzag_regression.py`](test_swing_zigzag_regression.py) | 📐 Regression baseline for swing and zigzag labelling. | 436 |
| [`test_replay_extend.py`](test_replay_extend.py) | ➕ Growing a replay past the snapshot it loaded. | 398 |
| [`test_follow_live_matrix.py`](test_follow_live_matrix.py) | 🔢 Every intraday timeframe, offset and date. | 321 |
| [`test_daily_weekly.py`](test_daily_weekly.py) | 📆 The `1d` and `1w` bars: trading-date grouping, the evening-open anchor, no session filter, no VWAP, and the weekend cut. | 290 |
| [`test_api_provider_errors.py`](test_api_provider_errors.py) | ⚠️ An unservable symbol is a **400**, not a 500. | 266 |
| [`test_reference_platform_parity.py`](test_reference_platform_parity.py) | 🎯 Parity against the reference platform, pinned to real printed bars. | 201 |
| [`test_store_persistence.py`](test_store_persistence.py) | 💾 Results survive a restart. | 258 |
| [`test_vwap_bands.py`](test_vwap_bands.py) | 📏 VWAP and its deviation bands. | 175 |
| [`test_symbol_universe.py`](test_symbol_universe.py) | 🔤 The symbol list stays coherent. | 117 |
| [`test_provider_timeframes.py`](test_provider_timeframes.py) | ⏱ Each provider serves what it claims. | 87 |
| [`test_schwab_redirect_parsing.py`](test_schwab_redirect_parsing.py) | 🏦 Schwab's redirect URL, parsed exactly. | 158 |
| [`test_replay_seek.py`](test_replay_seek.py) | ⏩ Seeking within a replay. | 66 |
| [`test_replay_session_message.py`](test_replay_session_message.py) | 💬 Session messages over the socket. | 120 |
| [`test_engine.py`](test_engine.py) | ▶️ Engine smoke tests on synthetic data. | 57 |
| [`_isolation_helpers.py`](_isolation_helpers.py) | A minimal result object. Underscore-prefixed so pytest ignores it. | 37 |


---

## 🗃 Subfolders

| Folder | ➜ What lives there |
|:--|:--|
| [`fixtures`](fixtures) | 📎 Pinned data the tests read |
| [`test_elliott_wave`](test_elliott_wave) | 🌊 The wave engine's own suite |


---

## 💡 Worth knowing

- ➜ **A refusal test not listed in `_SECURITY_SUITES` passes without reaching the guard.** [`conftest.py`](conftest.py) overrides `require_user` for every other suite.
- ➜ **Adding an API route fails two tests on purpose** — the OpenAPI guard sweep and an exact route count. Raise them deliberately, never by reflex.
- ➜ **A test that cannot fail defends nothing.** Run a new test against the commit that had the bug before trusting it.


---

<div align="center">

<sub>⬅ <a href="../README.md">Project README</a></sub>

</div>
