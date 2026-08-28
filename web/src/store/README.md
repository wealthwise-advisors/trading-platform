<div align="center">

# 🗃 Client State

**What the UI remembers between renders.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Does** | Holds the backtest configuration and the current page |
| 📦 **Library** | Zustand — one store, no provider tree |
| 🚫 **Not for** | Server data. That is React Query's job, in [`lib/api.ts`](../lib/api.ts) |
| 📁 **Path** | `web/src/store/` |
| 📦 **Holds** | `1` files · `131` lines |


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`configStore.ts`](configStore.ts) | ⚙️ Symbol, timeframe, strategy, dates, capital — and the active page. | 131 |


---

<div align="center">

<sub>⬅ <a href="../../../README.md">Project README</a> · <a href="..">web/src/</a></sub>

</div>
