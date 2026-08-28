<div align="center">

# 📋 Request & Response Models

**The shape of every payload, in one place.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Does** | Pydantic models — validation in, serialisation out |
| 🔗 **Mirrored by** | [`web/src/lib/types.ts`](../../web/src/lib/types.ts) |
| ⚠️ **Watch for** | Change a field here ➜ change it there, or the UI silently drops it |
| 📁 **Path** | `api/schemas/` |
| 📦 **Holds** | `5` files · `298` lines |


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`backtest.py`](backtest.py) | Run request, summary, trades, equity curve. | 116 |
| [`elliott_wave.py`](elliott_wave.py) | Wave structures and their measurements. | 65 |
| [`replay.py`](replay.py) | Replay session setup and per-bar frames. | 58 |
| [`optimize.py`](optimize.py) | Optimizer sweep request and ranked results. | 38 |
| [`schwab.py`](schwab.py) | Schwab auth status and callback payloads. | 21 |


---

<div align="center">

<sub>⬅ <a href="../../README.md">Project README</a> · <a href="..">api/</a></sub>

</div>
