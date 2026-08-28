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
| 📁 **Path** | `src/strategies/` |
| 📦 **Holds** | `6` files · `727` lines |


---

## 🔄 How it fits together

```
   base_strategy.py  (the interface)
        ▲
        ├── ma_crossover      ┐
        ├── rsi_divergence    │  any of these can be
        ├── rsi_mean_reversion├─ dropped into a run
        ├── breakout          │  without the engine
        └── regime_adaptive   ┘  knowing which it got

   parameters declared in api/strategy_registry.py ──► the optimiser sweeps them
```


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

## 💡 Worth knowing

- ➜ **Any strategy can be swapped for any other** because the engine only knows [`base_strategy.py`](base_strategy.py). Adding one means implementing that interface — no engine change.
- ➜ **Declare parameters in [`api/strategy_registry.py`](../../api/strategy_registry.py)** or the optimiser cannot sweep them, and the UI cannot draw the sliders.


---

<div align="center">

<sub>⬅ <a href="../../README.md">Project README</a> · <a href="..">src/</a></sub>

</div>
