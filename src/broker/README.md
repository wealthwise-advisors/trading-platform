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
| 📦 **Holds** | `3` files · `268` lines |


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`paper_broker.py`](paper_broker.py) | 🧾 The simulated broker used by backtests and paper trading. | 120 |
| [`base_broker.py`](base_broker.py) | The interface — orders in, fills out. | 74 |
| [`rithmic_broker.py`](rithmic_broker.py) | 📡 Live Rithmic adapter. | 74 |


---

<div align="center">

<sub>⬅ <a href="../../README.md">Project README</a> · <a href="..">src/</a></sub>

</div>
