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
| 📦 **Holds** | `4` files · `1,235` lines |


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
| [`ConfigForm.tsx`](ConfigForm.tsx) | ⚙️ The sidebar — source, symbol, timeframe, strategy, capital, dates, and the Session Hours clock. | 551 |
| [`ConfigParts.tsx`](ConfigParts.tsx) | 🧩 The pieces that form is built from, including `Section` and its accent table. | 306 |
| [`ResultsPage.tsx`](ResultsPage.tsx) | 📈 Stat cards, the tab bar, and every result view. | 298 |
| [`ConfigParts.a11y.test.tsx`](ConfigParts.a11y.test.tsx) | 🧪 Reads the rendered DOM, not the props: a slider's name has to reach the thumb, and help text may not sit in an `aria-label` on a bare span. | 80 |


---

## 💡 Worth knowing

- ➜ **The accent table lives in [`ConfigParts.tsx`](ConfigParts.tsx)** and its keys are named for the hue they draw, not the topic — a key that lies about its own colour is the one thing a reader will not check.
- ➜ **The Session Hours clock is display only.** ET/CT/MT/PT change what the two fields show and accept; `session_start` and `session_end` are always stored and sent as **Eastern**, because that pair anchors VWAP and is what a saved config and a report hold. Switching clocks therefore relabels a window rather than re-filtering one. The choice lives in `localStorage` under `session-hours-zone` and never reaches the config store or a request. See [`lib/sessionZone.ts`](../../lib/sessionZone.ts).
- ➜ **A control's name has to reach the element that carries the role.** `SliderField` passed `aria-label` to `<Slider>` from the start, and the thumb still had no name for months: Radix puts `role="slider"` on the thumb, so the label named the root instead. Nothing in the call site looked wrong. [`ConfigParts.a11y.test.tsx`](ConfigParts.a11y.test.tsx) asserts against the rendered DOM for exactly that reason.
- ➜ **Daily and weekly ignore Session Hours entirely.** A `1d` or `1w` bar already is a whole session, and Schwab stamps it at midnight — a 09:30–16:00 window would drop every one.


---

<div align="center">

<sub>⬅ <a href="../../../../README.md">Project README</a> · <a href="..">web/src/features/</a></sub>

</div>
