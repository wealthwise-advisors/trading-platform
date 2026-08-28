<div align="center">

# 🐍 The Trading Engine

**Every number the app reports is computed here. No HTTP, no UI.**

![pure%20python](https://img.shields.io/badge/pure%20python-no%20web-3776AB?style=flat-square&logo=python&logoColor=white) ![importable](https://img.shields.io/badge/importable-standalone-22c55e?style=flat-square)

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Does** | Data ➜ indicators ➜ strategy ➜ fills ➜ metrics |
| 🚫 **Knows nothing about** | FastAPI, React, sessions or users |
| ✅ **Why that matters** | It can be imported from a script, a notebook or a test with no server running |
| 📦 **Holds** | `1` files · `71` lines · `6` subfolders |


---

## 🔄 How it fits together

```
   data/          analysis/         strategies/       backtesting/     broker/
   ┌───────┐      ┌─────────┐      ┌───────────┐     ┌──────────┐    ┌────────┐
   │ bars  │ ───► │ signals │ ───► │  decide   │ ──► │  replay  │ ─► │ fills  │
   │ OHLCV │      │ RSI·EW  │      │ buy/sell  │     │  engine  │    │ + cost │
   └───────┘      └─────────┘      └───────────┘     └────┬─────┘    └────────┘
                                                          ▼
                                                    trades · equity · metrics
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`config.py`](config.py) | Reads `config/settings.yaml` and hands out typed settings. | 71 |


---

## 🗃 Subfolders

| Folder | ➜ What lives there |
|:--|:--|
| [`analysis/`](analysis) | 🔍 Indicators, swings, patterns and Elliott Wave |
| [`backtesting/`](backtesting) | ⏱ The engines that run those rules over history |
| [`broker/`](broker) | 💰 What a fill actually costs |
| [`data/`](data) | 📥 Where bars come from — Schwab, Rithmic, CSV, synthetic |
| [`live/`](live) | 📡 Live trading — a stub, deliberately |
| [`strategies/`](strategies) | 🧠 The rules that decide to buy or sell |


---

<div align="center">

<sub>⬅ <a href="../README.md">Project README</a></sub>

</div>
