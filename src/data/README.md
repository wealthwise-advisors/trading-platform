<div align="center">

# 📥 Market Data Providers

**Where bars come from. The engine never knows which one it got.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Does** | One interface, five sources |
| 📐 **Rule** | Every provider returns the same frame: `Datetime · Open · High · Low · Close · Volume` |
| ⏱ **Stored at** | 1-minute. Everything coarser is resampled at read time |
| 📁 **Path** | `src/data/` |
| 📦 **Holds** | `7` files · `1,363` lines · `1` subfolders |


---

## 🔄 How it fits together

```
   Schwab ──┐
   Rithmic ─┤
   CSV ─────┼──► base_provider ──► 1-minute bars ──► resample.py ──► 5m 15m 1h 1d
   External ┤                                        (never stored)
   Synthetic┘
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`schwab_provider.py`](schwab_provider.py) | 🏦 Historical OHLCV from the Charles Schwab market-data API. | 431 |
| [`rithmic_provider.py`](rithmic_provider.py) | 📡 Historical OHLCV via the Rithmic History API. | 267 |
| [`external_csv_provider.py`](external_csv_provider.py) | 📁 Your own CSV archive, pointed at by `settings.yaml`. | 261 |
| [`resample.py`](resample.py) | ⏱ **The one place** bars are aggregated up a timeframe. | 231 |
| [`sample_data.py`](sample_data.py) | 🎲 Synthetic OHLCV, so the app runs with no credentials at all. | 80 |
| [`base_provider.py`](base_provider.py) | The interface every provider satisfies. | 53 |
| [`csv_provider.py`](csv_provider.py) | The bundled sample archive. | 40 |


---

## 🗃 Subfolders

| Folder | ➜ What lives there |
|:--|:--|
| [`schwabdev/`](schwabdev) | Vendored Schwab SDK — third-party, not ours |


---

## 💡 Worth knowing

- ➜ **Only 1-minute bars are stored.** A 5m and a 15m chart derive from the same rows, so they cannot disagree with each other.
- ➜ **Session anchoring matters.** VWAP differences against another platform are usually the session window, not a bug — check Session Hours first.


---

<div align="center">

<sub>⬅ <a href="../../README.md">Project README</a> · <a href="..">src/</a></sub>

</div>
