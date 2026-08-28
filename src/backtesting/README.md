<div align="center">

# ⏱ Backtest & Replay Engines

**Run a strategy over history — all at once, or bar by bar.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Does** | Feeds bars to a strategy and records what happened |
| ⚖️ **Two modes** | **Backtest** runs to completion · **Replay** advances one bar at a time |
| 💰 **Costs** | Every fill is priced by [`src/broker`](../broker) — never at the close |
| 📦 **Holds** | `6` files · `1,539` lines |


---

## 🔄 How it fits together

```
   bars ──► strategy.on_bar() ──► signal ──► broker fill ──► portfolio
                                                                 │
                                    ┌────────────────────────────┘
                                    ▼
                        trades · equity curve · metrics
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`engine.py`](engine.py) | ▶️ The event-driven backtest engine. | 313 |
| [`replay_engine.py`](replay_engine.py) | ⏯ Step-by-step replay, one bar per call. | 308 |
| [`multi_replay.py`](multi_replay.py) | 🕐 Several replay engines advanced off **one shared clock**. | 655 |
| [`trade_quality.py`](trade_quality.py) | ⭐ A 0–100 setup score from entry-time context — never from the outcome. | 137 |
| [`results.py`](results.py) | The object a run returns: trades, equity, summary. | 80 |
| [`metrics.py`](metrics.py) | Sharpe, drawdown, win rate and the rest. | 46 |


---

## 💡 Worth knowing

- ➜ **`trade_quality.py` never looks at the result.** Scoring a setup by how it turned out would be hindsight with a number attached.


---

<div align="center">

<sub>⬅ <a href="../../README.md">Project README</a> · <a href="..">src/</a></sub>

</div>
