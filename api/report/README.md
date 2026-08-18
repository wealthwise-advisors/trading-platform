# 📈 `api/report`

**Charts rendered on the server.**

Used by the PDF and DOCX exports, which need an image rather than a live component.
Rendering server-side keeps an exported chart identical to the one on screen instead
of a second implementation that slowly drifts.

### Files in this directory

| File | Purpose | Lines |
|---|---|---:|
| [`report.py`](report.py) | Generate a self-contained HTML backtest report. | 1,168 |
| [`charts.py`](charts.py) | Plotly chart builders for the Streamlit dashboard. | 648 |

---

<sub>[⬅ Back to the project README](../../README.md)</sub>
