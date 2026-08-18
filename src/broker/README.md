# 💰 `src/broker`

**What a fill actually costs.**

A backtest that fills at the closing price flatters itself. This package charges for
every trade so the result is a plausible fill rather than an ideal one:

- ➜ **Commission** per contract, per side
- ➜ **Slippage** in ticks, applied against you
- ➜ **Tick rounding** to the instrument's real increment

The portfolio tracks position, realised and unrealised P&L, and the completed-trade
list cumulatively, so a single frame settles every scalar the UI needs.

### Files in this directory

| File | Purpose | Lines |
|---|---|---:|
| [`paper_broker.py`](paper_broker.py) | Simulated broker used by the backtesting engine and for paper trading. | 120 |
| [`base_broker.py`](base_broker.py) | The interface a broker implementation satisfies -- orders in, fills out. | 74 |
| [`rithmic_broker.py`](rithmic_broker.py) | Rithmic live broker adapter. | 74 |

---

<sub>[⬅ Back to the project README](../../README.md)</sub>
