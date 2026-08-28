<div align="center">

# 🎲 Sample Market Data

**Real 1-minute bars, 5,000 per instrument. Enough to run everything.**

![bars](https://img.shields.io/badge/bars-5%2C000%20each-22c55e?style=flat-square) ![size](https://img.shields.io/badge/size-4.2%20MB-0ea5e9?style=flat-square) ![source](https://img.shields.io/badge/source-real%20history-7c6cf5?style=flat-square)

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Why committed** | The platform runs end to end with **no credentials and no download** |
| 📊 **What they are** | Genuine market history, not synthetic — so the analysis engine works on real structure |
| 📦 **Full archive** | [`wealthwise-advisors/data`](https://github.com/wealthwise-advisors/data) — 433 MB, 7.9M bars, Git LFS |
| ⚙️ **Point at the full set** | `data.external_dir` in [`config/settings.yaml`](../../config/settings.yaml) |
| 📁 **Path** | `data/sample/` |
| 📦 **Holds** | `16` files · `76,631` lines |


---

## 🔄 How it fits together

```
   17 files · 5,000 rows each
        │
        ▼
   enough for: the test suite · a first run · a demo with no credentials
   not enough for: a real backtest ──► clone wealthwise-advisors/data
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`ES_FULL.csv`](ES_FULL.csv) | 📈 E-mini S&P 500 — 2008-01-02 → 2008-01-08 | 5,001 |
| [`ES_FULL_2022.csv`](ES_FULL_2022.csv) | 📈 E-mini S&P 500 — 2022 | 5,001 |
| [`ES_FULL_2023.csv`](ES_FULL_2023.csv) | 📈 E-mini S&P 500 — 2023 | 5,001 |
| [`ES_FULL_2024.csv`](ES_FULL_2024.csv) | 📈 E-mini S&P 500 — 2024 | 5,001 |
| [`ES_FULL_2025.csv`](ES_FULL_2025.csv) | 📈 E-mini S&P 500 — 2025 | 5,001 |
| [`GC_FULL.csv`](GC_FULL.csv) | 🥇 Gold — 2025-06-22 → 2025-06-26 | 5,001 |
| [`FULL_AAPL.csv`](FULL_AAPL.csv) | 🍎 Apple | 5,001 |
| [`FULL_AMD.csv`](FULL_AMD.csv) | 🔴 AMD | 5,001 |
| [`FULL_COIN.csv`](FULL_COIN.csv) | 🪙 Coinbase | 5,001 |
| [`FULL_CRWV.csv`](FULL_CRWV.csv) | ☁️ CoreWeave | 5,001 |
| [`FULL_META.csv`](FULL_META.csv) | 🔵 Meta | 5,001 |
| [`FULL_NVDA.csv`](FULL_NVDA.csv) | 🟩 NVIDIA | 5,001 |
| [`FULL_SMCI.csv`](FULL_SMCI.csv) | 🖥 Super Micro | 5,001 |
| [`FULL_TSLA.csv`](FULL_TSLA.csv) | 🚗 Tesla | 5,001 |
| [`FULL_UPST.csv`](FULL_UPST.csv) | 💳 Upstart | 5,001 |
| [`BTC_FULL.csv`](BTC_FULL.csv) | ₿ Bitcoin — 1,615 bars | 1,616 |


---

## 💡 Worth knowing

- ➜ **These ship so the project works with no credentials and no download.** A repository that cannot run until you have an API key cannot be evaluated.


---

<div align="center">

<sub>⬅ <a href="../../README.md">Project README</a> · <a href="..">data/</a></sub>

</div>
