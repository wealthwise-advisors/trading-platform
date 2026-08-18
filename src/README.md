# 🐍 `src`

**The engine. Everything that turns bars into a result.**

No web framework, no HTTP, no React — this layer knows nothing about how it is
called. That separation is deliberate: the same analysis runs from a test, from the
API, and from a script, and gets the same answer each time.

### The packages

| Package | What it owns |
|---|---|
| [`analysis/`](analysis) | Reading the market — waves, patterns, indicators, regime |
| [`strategies/`](strategies) | Turning that reading into buy and sell decisions |
| [`backtesting/`](backtesting) | Replaying history bar by bar, on one shared clock |
| [`broker/`](broker) | Charging for fills — commission, slippage, tick rounding |
| [`data/`](data) | Getting bars in, and aggregating them **one** way |
| [`live/`](live) | The live loop (experimental) |

### The rule that shapes this layer

**One aggregator.** Bar aggregation lives only in [`data/resample.py`](data/resample.py).
It used to be duplicated across three providers, and the copy that forgot to anchor to
the session open kept reintroducing shifted bars on whichever path happened to reach
it. Every timeframe in the app now derives from that single function.

### Files in this directory

| File | Purpose | Lines |
|---|---|---:|
| [`config.py`](config.py) | Load and merge settings.yaml with optional credentials.yaml. | 71 |

### Subdirectories

| Directory | Files |
|---|---:|
| [`analysis/`](analysis) | 20 |
| [`backtesting/`](backtesting) | 7 |
| [`broker/`](broker) | 4 |
| [`data/`](data) | 11 |
| [`live/`](live) | 2 |
| [`strategies/`](strategies) | 7 |

---

<sub>[⬅ Back to the project README](../README.md)</sub>
