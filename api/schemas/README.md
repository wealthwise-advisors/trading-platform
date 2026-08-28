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

## 🔄 How it fits together

```
   web/src/lib/types.ts          api/schemas/*.py
   ┌────────────────┐            ┌────────────────┐
   │  TypeScript    │ ◄────────► │    Pydantic    │
   │  the UI reads  │  MUST      │  the API sends │
   └────────────────┘  MATCH     └────────────────┘
                                         │
        change one without the other     ▼
        and the field is dropped    validate ──► 422
        in silence                  on the way in
```


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

## 💡 Worth knowing

- ➜ **These models are half of a contract.** The other half is [`web/src/lib/types.ts`](../../web/src/lib/types.ts) — change a field here without changing it there and the UI drops it silently, with no error anywhere.
- ➜ **Validation failures are 422, not 500.** A malformed request is the caller's problem and must say which field; a 500 would claim it was ours.


---

<div align="center">

<sub>⬅ <a href="../../README.md">Project README</a> · <a href="..">api/</a></sub>

</div>
