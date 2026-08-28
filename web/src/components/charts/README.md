<div align="center">

# 📈 Charts

**Plotly wrappers. Every one is dark-theme first.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Does** | Turns result data into figures |
| 📦 **Library** | Plotly, loaded once and shared |
| 🎨 **Colours** | Cool for chrome; red and green kept for **meaning** |
| 📁 **Path** | `web/src/components/charts/` |
| 📦 **Holds** | `6` files · `2,149` lines |


---

## 🔄 How it fits together

```
   backtest result ──► serialisers ──► JSON ──► these components ──► Plotly

   CandlestickChart   price · VWAP · volume profile · swings · trades
   ElliottWaveChart   structures drawn over price
   EquityChart        equity + drawdown
   PnlDistribution    where the trades landed
   MonthlyReturns     returns by month
   WinLossDonut       the split

   colour rule: chrome is cool · red and green are kept for MEANING
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`CandlestickChart.tsx`](CandlestickChart.tsx) | 🕯 The main price chart — candles, VWAP, volume profile, swings, trades. | 1,420 |
| [`ElliottWaveChart.tsx`](ElliottWaveChart.tsx) | 🌊 Wave structures drawn over price. | 517 |
| [`EquityChart.tsx`](EquityChart.tsx) | 💹 Equity curve and drawdown. | 66 |
| [`PnlDistributionChart.tsx`](PnlDistributionChart.tsx) | 📊 Trade P&L distribution. | 55 |
| [`MonthlyReturnsHeatmap.tsx`](MonthlyReturnsHeatmap.tsx) | 📅 Returns by month. | 61 |
| [`WinLossDonut.tsx`](WinLossDonut.tsx) | 🍩 Win/loss split. | 30 |


---

## 💡 Worth knowing

- ➜ **Red and green are reserved for meaning** — a loss and a gain. Recolouring them to match the theme would delete information from the chart.


---

<div align="center">

<sub>⬅ <a href="../../../../README.md">Project README</a> · <a href="..">web/src/components/</a></sub>

</div>
