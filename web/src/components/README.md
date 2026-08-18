# 🎨 `web/src/components`

**Shared UI.**

`ui/` holds the shadcn/ui primitives — button, select, table, dialog and friends,
built on Radix. Everything above that is app-specific and composed from them.

### Files in this directory

| File | Purpose | Lines |
|---|---|---:|
| [`DeviationColorSettings.tsx`](DeviationColorSettings.tsx) | Colour picker for the VWAP deviation groups. | 119 |
| [`SchwabAuthWidget.tsx`](SchwabAuthWidget.tsx) | Port of ui/app.py's sidebar Schwab widget: status check, then the | 102 |
| [`DayCountStepper.tsx`](DayCountStepper.tsx) | "Number of Days" stepper, shared by Live Replay and Backtest. | 79 |
| [`SavedConfigsPanel.tsx`](SavedConfigsPanel.tsx) | Save, list and reload a run configuration so a setup can be returned to. | 65 |
| [`StatusBanner.tsx`](StatusBanner.tsx) | The connection and session state shown above the workspace. | 27 |

### Subdirectories

| Directory | Files |
|---|---:|
| [`cards/`](cards) | 3 |
| [`charts/`](charts) | 7 |
| [`tables/`](tables) | 4 |
| [`ui/`](ui) | 14 |

---

<sub>[⬅ Back to the project README](../../../README.md)</sub>
