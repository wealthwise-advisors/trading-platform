<div align="center">

# 📊 Backtest Screen

**Configure a run on the left, read the results on the right.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Does** | The main screen of the application |
| 🔗 **Talks to** | `POST /api/backtests`, then the result sub-resources |
| 📁 **Path** | `web/src/features/backtest/` |
| 📦 **Holds** | `3` files · `1,018` lines |


---

## 🔄 How it fits together

```
   ConfigForm  ──► POST /api/backtests ──► backtest_id
        │                                      │
   ConfigParts                                 ▼
   (Section, sliders,                   ResultsPage
    the accent table)                    ├── stat cards
                                         └── tabs ──► charts · tables
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`ConfigForm.tsx`](ConfigForm.tsx) | ⚙️ The sidebar — source, symbol, timeframe, strategy, capital, dates. | 431 |
| [`ConfigParts.tsx`](ConfigParts.tsx) | 🧩 The pieces that form is built from, including `Section` and its accent table. | 289 |
| [`ResultsPage.tsx`](ResultsPage.tsx) | 📈 Stat cards, the tab bar, and every result view. | 298 |


---

## 💡 Worth knowing

- ➜ **The accent table lives in [`ConfigParts.tsx`](ConfigParts.tsx)** and its keys are named for the hue they draw, not the topic — a key that lies about its own colour is the one thing a reader will not check.


---

<div align="center">

<sub>⬅ <a href="../../../../README.md">Project README</a> · <a href="..">web/src/features/</a></sub>

</div>
