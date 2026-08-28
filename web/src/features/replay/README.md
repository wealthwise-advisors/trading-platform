<div align="center">

# 📡 Market Grid

**Live and replayed bars, several timeframes off one clock.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Does** | Streams bars over a WebSocket and draws them as they arrive |
| 🕐 **One clock** | Every timeframe advances off a single shared clock — see [`src/backtesting/multi_replay.py`](../../../../src/backtesting/multi_replay.py) |
| 📡 **Follow live** | Once caught up, it keeps asking for bars that have since formed |
| 📁 **Path** | `web/src/features/replay/` |
| 📦 **Holds** | `5` files · `3,024` lines |


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`ReplayPage.tsx`](ReplayPage.tsx) | 🖥 The screen itself — grid, controls, follow-live, VWAP settings. | 2,623 |
| [`SetupPanels.tsx`](SetupPanels.tsx) | 🎛 The setup panels before a session starts. | 134 |
| [`SetupFields.tsx`](SetupFields.tsx) | 📝 Individual setup inputs. | 45 |
| [`SetupChrome.tsx`](SetupChrome.tsx) | 🖼 Framing and decoration for setup. | 128 |
| [`StepSection.tsx`](StepSection.tsx) | 🔢 The numbered setup steps. | 94 |


---

<div align="center">

<sub>⬅ <a href="../../../../README.md">Project README</a> · <a href="..">web/src/features/</a></sub>

</div>
