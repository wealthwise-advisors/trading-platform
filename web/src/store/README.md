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

## 🔄 How it fits together

```
   configStore (Zustand)          React Query (lib/api.ts)
   ┌────────────────────┐         ┌────────────────────┐
   │ what YOU chose     │         │ what the SERVER    │
   │ symbol, timeframe  │         │ returned           │
   │ strategy, dates    │         │ bars, trades       │
   └────────────────────┘         └────────────────────┘
        client state                   server state
        ╳ do not put server data here -- it will go stale
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`configStore.ts`](configStore.ts) | ⚙️ Symbol, timeframe, strategy, dates, capital — and the active page. | 131 |


---

## 💡 Worth knowing

- ➜ **Client state only.** Server data belongs to React Query in [`lib/api.ts`](../lib/api.ts) — duplicating it here guarantees the two go out of step.


---

<div align="center">

<sub>⬅ <a href="../../../README.md">Project README</a> · <a href="..">web/src/</a></sub>

</div>
