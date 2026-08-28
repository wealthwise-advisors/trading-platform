<div align="center">

# 🃏 Cards

**The small panels that carry one number or one idea.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Does** | Consistent framing for stats and notes |
| 🎨 **Accents** | `ACCENTS` in [`StatCard.tsx`](StatCard.tsx) — all cool, by design |
| 📁 **Path** | `web/src/components/cards/` |
| 📦 **Holds** | `4` files · `374` lines |


---

## 🔄 How it fits together

```
   StatCard    one headline number + accent      ┐
   StatTile    denser, for a grid of numbers     ├─ same framing,
   InfoCard    a list of label/value rows        │  so a screen of
   ChartLegend what a chart's colours mean       ┘  them looks like one thing

   ACCENTS[] in StatCard.tsx -- all six are cool, deliberately.
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`StatCard.tsx`](StatCard.tsx) | 📊 One headline number, with an icon and an accent. | 54 |
| [`StatTile.tsx`](StatTile.tsx) | 🔢 A denser tile for grids of numbers. | 155 |
| [`InfoCard.tsx`](InfoCard.tsx) | 📋 Performance summary, backtest details and insights. | 89 |
| [`ChartLegendCard.tsx`](ChartLegendCard.tsx) | 🏷 Explains what a chart's colours mean. | 76 |


---

## 💡 Worth knowing

- ➜ **All six accents are cool, deliberately.** The app sits on a warm background, and the interface has to read as the other thing on screen.


---

<div align="center">

<sub>⬅ <a href="../../../../README.md">Project README</a> · <a href="..">web/src/components/</a></sub>

</div>
