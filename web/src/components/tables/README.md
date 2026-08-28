<div align="center">

# 📋 Tables

**Rows of results, with the same header treatment everywhere.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 📁 **Path** | `web/src/components/tables/` |
| 📦 **Holds** | `4` files · `320` lines |


---

## 🔄 How it fits together

```
   result data ──► one <thead> treatment ──► every table looks like the others

   TradeLogTable              every trade the run produced
   OptimizerPanel             ranked sweeps, best first
   CandlestickPatternsTable   detected candle patterns
   ChartPatternsTable         detected chart patterns
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`TradeLogTable.tsx`](TradeLogTable.tsx) | 📒 Every trade a run produced. | 64 |
| [`OptimizerPanel.tsx`](OptimizerPanel.tsx) | 🎯 Ranked parameter sweeps — best first. | 118 |
| [`CandlestickPatternsTable.tsx`](CandlestickPatternsTable.tsx) | 🕯 Detected candlestick patterns. | 74 |
| [`ChartPatternsTable.tsx`](ChartPatternsTable.tsx) | 📐 Detected chart patterns. | 64 |


---

## 💡 Worth knowing

- ➜ **One header treatment across all four**, so a screen showing two of them reads as one interface rather than two.


---

<div align="center">

<sub>⬅ <a href="../../../../README.md">Project README</a> · <a href="..">web/src/components/</a></sub>

</div>
