# ⏱ `src/backtesting`

**Replaying history bar by bar, honestly.**

### One clock, many timeframes

The obvious implementation — keep N engines and step them all once per tick — does
not produce a synchronised view. `step()` advances one *bar*, and a bar is a
different amount of time on each timeframe: after 100 ticks a 1m pane has moved 100
minutes while a 1h pane has moved 100 hours.

So the clock is measured in **market time**. One tick advances time by exactly one
base bar, and every other timeframe steps only when its next bar has *closed*. Every
pane therefore shows the same instant, and coarse panes simply update less often —
which is how a real multi-timeframe terminal behaves.

### Never a bar that has not closed

`trim_to_closed_bars` makes two cuts: the still-forming source bar, and any trailing
*base* bin that is only partly covered. The second one is easy to miss and was a real
bug — with 1m data and a 5m base, trimming to 12:15 leaves a 5m bin holding a single
minute, which the clock then emits as a closed five-minute bar.

### Files in this directory

| File | Purpose | Lines |
|---|---|---:|
| [`multi_replay.py`](multi_replay.py) | Multi-timeframe replay: several ReplayEngine instances advanced off ONE shared market clock. | 637 |
| [`engine.py`](engine.py) | Event-driven backtesting engine for futures. | 313 |
| [`replay_engine.py`](replay_engine.py) | Step-by-step replay engine. | 308 |
| [`trade_quality.py`](trade_quality.py) | Post-hoc "setup quality" score (0-100) for each executed trade, based on entry-time context -- NOT on the… | 137 |
| [`results.py`](results.py) | The result object a backtest returns -- trades, equity curve and summary. | 80 |
| [`metrics.py`](metrics.py) | Performance metrics computed from a completed run. | 46 |

---

<sub>[⬅ Back to the project README](../../README.md)</sub>
