# 🔍 `src/analysis`

**Reading what the market is doing.**

Pure measurement. Nothing here decides to trade — it describes structure, and the
strategies decide what to do about it.

Every function takes a DataFrame of bars and returns a description. No I/O, no
global state, no hidden configuration, which is what lets the same call be trusted
from a test and from a live session.

### Files in this directory

| File | Purpose | Lines |
|---|---|---:|
| [`swing_identification.py`](swing_identification.py) | Swing (pivot) detection for price-action and divergence strategies. | 401 |
| [`zigzag.py`](zigzag.py) | ZigZag pivot detection and per-swing decimal labeling, extracted verbatim from ui/components/charts.py so the… | 301 |
| [`indicators.py`](indicators.py) | RSI and Stochastic calculations, extracted verbatim from ui/components/charts.py so the FastAPI backend and… | 300 |
| [`candlestick_patterns.py`](candlestick_patterns.py) | Rule-based candlestick pattern detection: Doji, Hammer, Bullish/Bearish Engulfing, Morning Star, Evening Star. | 160 |
| [`chart_patterns.py`](chart_patterns.py) | Rule-based classic chart pattern detection built on the confirmed swing pivots from swing_identification.py:… | 145 |
| [`regime.py`](regime.py) | Classify the current market regime from trailing OHLC bars: trending (up or down), sideways/choppy, or… | 82 |

### Subdirectories

| Directory | Files |
|---|---:|
| [`elliott_wave/`](elliott_wave) | 13 |

---

<sub>[⬅ Back to the project README](../../README.md)</sub>
