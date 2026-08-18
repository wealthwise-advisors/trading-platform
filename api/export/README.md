# 📤 `api/export`

**Getting results out — CSV, XLSX, PDF, DOCX.**

Four formats because four audiences: a spreadsheet for analysis, a PDF for reading,
a DOCX for editing, and CSV for whatever comes next.

### Files in this directory

| File | Purpose | Lines |
|---|---|---:|
| [`formats.py`](formats.py) | Shared multi-format export helpers -- turn one or more labeled DataFrames into CSV, Excel, PDF, or Word bytes. | 117 |
| [`report_export.py`](report_export.py) | Builds the DataFrames used by the multi-format backtest report export (CSV/Excel/PDF/Word) -- a metrics… | 54 |

---

<sub>[⬅ Back to the project README](../../README.md)</sub>
