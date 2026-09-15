<div align="center">

# 📈 Report Rendering

**Charts and documents built on the server, not in the browser.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Does** | Renders a finished backtest into a shareable report |
| 🖼 **Why server-side** | A report must look identical wherever it is opened |
| 📁 **Path** | `api/report/` |
| 📦 **Holds** | `3` files · `2,264` lines |


---

## 🔄 How it fits together

```
   BacktestResults          chart settings (from the live chart)
        │                          │
        ▼                          ▼
   charts.py ──► figures ──┐   chart_settings_draw.py
                           ├──► report.py ──► one self-contained .html
   summary · trades ───────┘                  (opens anywhere, same look)
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`report.py`](report.py) | Assembles the full HTML report — sections, tables, verdicts. | 1,188 |
| [`chart_settings_draw.py`](chart_settings_draw.py) | Draws the oscillator rows and Volume Profile with the live chart's own settings. | 407 |
| [`charts.py`](charts.py) | Indicator helpers the report imports, plus an older fixed layout no export uses. | 669 |


---

## 💡 Worth knowing

- ➜ **Rendered on the server, on purpose.** A report is shared, and it has to look the same wherever it is opened — not depend on the reader's browser or fonts.
- ➜ **The report never recomputes.** It formats a finished `BacktestResults`; if a number here disagreed with the screen, one of them would be lying.
- ➜ **It draws what the chart shows.** Export Report sends the chart's settings: which oscillators are on, and every Volume Profile option.
- ➜ **Mirrored line for line.** `chart_settings_draw.py` copies the web code, so change both sides together.
- ➜ **Pinned by two shared files.** `tests/fixtures/chart_settings_factory.json` holds the defaults, and `volume_profile_golden.json` holds the exact profile numbers.
- ➜ **Charts in HTML only.** CSV, Excel, PDF and Word carry the summary and trade log.


---

<div align="center">

<sub>⬅ <a href="../../README.md">Project README</a> · <a href="..">api/</a></sub>

</div>
