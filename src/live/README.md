<div align="center">

# 📡 Live Trading

**A stub, on purpose. Nothing here places a real order.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Status** | ⚠️ **Not implemented.** The Deploy button is disabled to match |
| 🤔 **Why a stub** | A half-built order path that looks finished is worse than an honest gap |
| 📁 **Path** | `src/live/` |
| 📦 **Holds** | `1` files · `96` lines |


---

## 🔄 How it fits together

```
   src/backtesting ──► PaperBroker ──► simulated fills        ✅ works

   src/live/trader.py ──► RithmicBroker ──► real orders       ⚠️ STUB
        ▲
        └── the Deploy button is disabled to match. A half-built order
            path that LOOKS finished is worse than an honest gap.
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`trader.py`](trader.py) | The shape a live trader would take. Does not trade. | 96 |


---

## 💡 Worth knowing

- ➜ **This is a stub and stays one until it is genuinely finished.** The Deploy button in the UI is disabled to match, so nothing in the product implies it works.
- ➜ **The paper broker is the tested path.** Backtesting and paper trading both run through [`src/broker/paper_broker.py`](../broker/paper_broker.py).


---

<div align="center">

<sub>⬅ <a href="../../README.md">Project README</a> · <a href="..">src/</a></sub>

</div>
