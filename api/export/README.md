<div align="center">

# 📤 File Writers

**One backtest, four file formats.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Does** | CSV · XLSX · PDF · DOCX from the same result object |
| 📐 **Rule** | A writer formats. It never re-computes a number |
| 📁 **Path** | `api/export/` |
| 📦 **Holds** | `2` files · `171` lines |


---

## 🔄 How it fits together

```
                    ┌──► CSV    formats.py
   BacktestResults ─┼──► XLSX   formats.py
   (already final)  ├──► PDF    report_export.py
                    └──► DOCX   report_export.py

   ╳ no writer recomputes a number. It formats what it was given.
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`formats.py`](formats.py) | The writers themselves, one per format. | 117 |
| [`report_export.py`](report_export.py) | Wraps a rendered report into a downloadable file. | 54 |


---

## 💡 Worth knowing

- ➜ **A writer formats, it never calculates.** Four formats reading one result object is the only way they cannot disagree with each other.


---

<div align="center">

<sub>⬅ <a href="../../README.md">Project README</a> · <a href="..">api/</a></sub>

</div>
