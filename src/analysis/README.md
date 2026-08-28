<div align="center">

# 🔍 Indicators & Pattern Detection

**Everything derived from price, before a strategy sees it.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Does** | Bars in ➜ indicators, pivots, patterns and waves out |
| 🧪 **Guarded by** | [`tests/test_indicator_correctness.py`](../../tests/test_indicator_correctness.py) — 1,069 lines |
| 📐 **Rule** | Pure functions on a frame. No I/O, no state |
| 📁 **Path** | `src/analysis/` |
| 📦 **Holds** | `6` files · `1,389` lines · `1` subfolders |


---

## 🔄 How it fits together

```
   bars
    │
    ├──► indicators.py ──────► RSI · Stochastic
    ├──► swing_identification ──► pivots ──┬──► chart_patterns.py
    │                                      └──► elliott_wave/
    ├──► zigzag.py ─────────► labelled swings (1.1, 1.2 …)
    ├──► candlestick_patterns ► Doji · Hammer · Engulfing
    └──► regime.py ─────────► trending up · down · choppy

   every one is a pure function of a frame. No I/O, no state.
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`swing_identification.py`](swing_identification.py) | ⛰ Swing (pivot) detection for price-action and divergence. | 401 |
| [`zigzag.py`](zigzag.py) | 📐 ZigZag pivots and per-swing decimal labelling (1.1, 1.2 …). | 301 |
| [`indicators.py`](indicators.py) | 📊 RSI, Stochastic and friends. | 300 |
| [`candlestick_patterns.py`](candlestick_patterns.py) | 🕯 Doji · Hammer · Engulfing · Morning/Evening Star. | 160 |
| [`chart_patterns.py`](chart_patterns.py) | 📈 Classic patterns built on confirmed swing pivots. | 145 |
| [`regime.py`](regime.py) | 🌤 Trending up, trending down, or choppy. | 82 |


---

## 🗃 Subfolders

| Folder | ➜ What lives there |
|:--|:--|
| [`elliott_wave/`](elliott_wave) | 🌊 The full Elliott Wave engine — 13 modules |


---

## 💡 Worth knowing

- ➜ **Every function here is pure.** Same frame in, same numbers out — which is what makes [`tests/test_indicator_correctness.py`](../../tests/test_indicator_correctness.py) able to pin them at all.
- ➜ **Swing pivots are shared, not recomputed.** Chart patterns and the wave engine both build on `swing_identification`, so they cannot disagree about where a swing is.


---

<div align="center">

<sub>⬅ <a href="../../README.md">Project README</a> · <a href="..">src/</a></sub>

</div>
