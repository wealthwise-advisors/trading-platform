<div align="center">

# 📄 Generated Reports

**Output only. Nothing here is source.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Holds** | Reports written by [`api/report`](../api/report) and [`api/export`](../api/export) |
| 🚫 **Gitignored** | Safe to delete at any time — it regenerates |
| 📁 **Path** | `reports/` |


---

## 🔄 How it fits together

```
   api/report  ──┐
                 ├──► reports/exports/  ──► the browser downloads it
   api/export  ──┘

   gitignored · regenerates · safe to delete at any time
```


---

## 🗃 Subfolders

| Folder | ➜ What lives there |
|:--|:--|
| [`exports/`](exports) | 📤 CSV · XLSX · PDF · DOCX written on request |


---

## 💡 Worth knowing

- ➜ **Output only, and gitignored.** Deleting the whole folder loses nothing — it regenerates on the next export.


---

<div align="center">

<sub>⬅ <a href="../README.md">Project README</a></sub>

</div>
