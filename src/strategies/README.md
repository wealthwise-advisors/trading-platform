# 🧠 `src/strategies`

**Turning a reading of the market into a decision.**

Every strategy implements the same interface from [`base_strategy.py`](base_strategy.py),
so any of them can be dropped into a backtest or a replay without the engine knowing
which one it is holding.

### Stateful on purpose

A strategy is allowed to remember. RSI divergence arms a setup on one bar and
confirms it several bars later, which is why **each timeframe gets its own instance**
— sharing one across timeframes would let an hourly bar overwrite the one-minute
strategy's pre-conditions and silently change its signals.

### Files in this directory

| File | Purpose | Lines |
|---|---|---:|
| [`rsi_divergence.py`](rsi_divergence.py) | RSI Divergence Strategy ======================= Based on strategy_original_first.py and strategy_six.py. | 308 |
| [`breakout.py`](breakout.py) | Donchian Channel breakout strategy (common in futures trend-following). | 106 |
| [`regime_adaptive.py`](regime_adaptive.py) | Regime-adaptive strategy: auto-switches trading logic based on the current market regime… | 104 |
| [`rsi_mean_reversion.py`](rsi_mean_reversion.py) | RSI mean-reversion strategy. | 99 |
| [`ma_crossover.py`](ma_crossover.py) | Moving Average Crossover strategy (fast MA crosses above/below slow MA). | 65 |
| [`base_strategy.py`](base_strategy.py) | The interface every strategy implements, so any of them can be swapped into a run. | 45 |

---

<sub>[⬅ Back to the project README](../../README.md)</sub>
