<div align="center">

# 🧠 Trading Strategies

**The rules that decide. Swap any one for any other.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Does** | Bars + indicators ➜ buy, sell or hold |
| 🔌 **Interface** | Implement [`base_strategy.py`](base_strategy.py) and the engine can run it |
| 🎛 **Parameters** | Declared in [`api/strategy_registry.py`](../../api/strategy_registry.py) so the optimiser can sweep them |
| 📦 **Holds** | `6` files · `727` lines |


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`rsi_divergence.py`](rsi_divergence.py) | 📉 RSI divergence against confirmed swing pivots. | 308 |
| [`breakout.py`](breakout.py) | 📊 Donchian channel breakout. | 106 |
| [`regime_adaptive.py`](regime_adaptive.py) | 🌤 Switches logic based on the detected regime. | 104 |
| [`rsi_mean_reversion.py`](rsi_mean_reversion.py) | ↩️ Fade the extreme. | 99 |
| [`ma_crossover.py`](ma_crossover.py) | ✂️ Fast MA crosses slow MA. | 65 |
| [`base_strategy.py`](base_strategy.py) | The interface every strategy implements. | 45 |


---

<div align="center">

<sub>⬅ <a href="../../README.md">Project README</a> · <a href="..">src/</a></sub>

</div>
