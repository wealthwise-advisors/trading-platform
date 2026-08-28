<div align="center">

# 💰 Broker & Execution Costs

**What a fill actually costs. A backtest that fills at the close flatters itself.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Does** | Charges every trade so the result is a plausible fill, not an ideal one |
| 💸 **Charges** | Commission per contract per side · slippage in ticks · tick rounding |
| 📊 **Tracks** | Position, realised and unrealised P&L, and completed trades — cumulatively |
| 📁 **Path** | `src/broker/` |
| 📦 **Holds** | `3` files · `268` lines |


---

## 🔄 How it fits together

```
   signal ──► order ──► ┌─────────────────┐ ──► fill
                        │  commission     │
                        │  + slippage     │   a backtest that fills
                        │  + tick round   │   at the close flatters
                        └─────────────────┘   itself
                                 │
                                 ▼
                        position · realised · unrealised · trade list
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`paper_broker.py`](paper_broker.py) | 🧾 The simulated broker used by backtests and paper trading. | 120 |
| [`base_broker.py`](base_broker.py) | The interface — orders in, fills out. | 74 |
| [`rithmic_broker.py`](rithmic_broker.py) | 📡 Live Rithmic adapter. | 74 |


---

## 💡 Worth knowing

- ➜ **Filling at the closing price is the most common way a backtest lies.** Every fill here is charged commission, slippage and tick rounding, so the equity curve is a plausible one rather than an ideal one.
- ➜ **The portfolio is tracked cumulatively**, so a single frame settles every number the UI needs — no second pass to reconcile.


---

<div align="center">

<sub>⬅ <a href="../../README.md">Project README</a> · <a href="..">src/</a></sub>

</div>
