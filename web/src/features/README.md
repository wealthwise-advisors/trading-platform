<div align="center">

# 🖼 Application Pages

**One folder per screen. Nothing shared lives here.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Rule** | Used by two screens? It belongs in [`components/`](../components) |
| 🧭 **Routing** | These are tabs within one document, switched in [`App.tsx`](../App.tsx) |
| 📁 **Path** | `web/src/features/` |


---

## 🔄 How it fits together

```
   App.tsx
     ├──► backtest/   configure a run, read its results
     ├──► replay/     Market Grid, live and replayed bars
     └──► export/     raw OHLC download

   these are tabs within ONE document, not routes.
   ╳ anything used by two of them belongs in components/
```


---

## 🗃 Subfolders

| Folder | ➜ What lives there |
|:--|:--|
| [`backtest/`](backtest) | 📊 Configure a run and read its results |
| [`export/`](export) | 📤 Raw OHLC download |
| [`replay/`](replay) | 📡 Market Grid — live and replayed bars |


---

## 💡 Worth knowing

- ➜ **These are tabs within one document**, not routed pages — which is why the app background is set once, at the shell.


---

<div align="center">

<sub>⬅ <a href="../../../README.md">Project README</a> · <a href="..">web/src/</a></sub>

</div>
