<div align="center">

# 📤 Export Screen

**Raw OHLC out, no backtest required.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Does** | Symbol + range + source ➜ CSV · Excel · PDF · Word |
| 🔗 **Talks to** | `GET /api/data/export` |
| 📁 **Path** | `web/src/features/export/` |
| 📦 **Holds** | `1` files · `164` lines |


---

## 🔄 How it fits together

```
   pick symbol · timeframe · date range · source
        │
        ▼
   GET /api/data/export ──► api/export/ ──► CSV · XLSX · PDF · DOCX

   ╳ no backtest is run. This is the raw bars.
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`DataExportPage.tsx`](DataExportPage.tsx) | 📤 The form and the download. | 164 |


---

## 💡 Worth knowing

- ➜ **No backtest is run.** This is the raw bars, which is why it is a separate screen rather than a button on the results page.


---

<div align="center">

<sub>⬅ <a href="../../../../README.md">Project README</a> · <a href="..">web/src/features/</a></sub>

</div>
