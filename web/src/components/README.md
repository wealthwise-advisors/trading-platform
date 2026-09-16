<div align="center">

# 🎨 Shared UI Components

**Everything used in more than one place.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Holds** | Reusable pieces. Anything page-specific lives in [`features/`](../features) |
| 🎨 **Base kit** | shadcn/ui in [`ui/`](ui) — do not edit those by hand |
| 📁 **Path** | `web/src/components/` |
| 📦 **Holds** | `22` files · `3,273` lines · `5` subfolders |


---

## 🔄 How it fits together

```
   used on ONE screen  ──► features/<that screen>/
   used on TWO or more ──► components/          ◄── you are here
   no JSX at all       ──► lib/

   components/
     ├── ui/      shadcn primitives  ── everything is built from these
     ├── cards/   one number, framed
     ├── charts/  Plotly wrappers
     ├── tables/  rows of results
     └── motion/  shared timings
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`SymbolMark.tsx`](SymbolMark.tsx) | 🏷 The instrument badge. Each contract keeps its own identity colour. | 414 |
| [`AccountSettings.tsx`](AccountSettings.tsx) | 👤 The account screen — profile, password, and deleting the account. | 264 |
| [`InstrumentPicker.tsx`](InstrumentPicker.tsx) | 🔍 Searchable symbol chooser. | 261 |
| [`IntervalPicker.tsx`](IntervalPicker.tsx) | ⏱ The interval popup — fifteen rows as `days : interval`, starrable and reorderable. | 256 |
| [`Onboarding.tsx`](Onboarding.tsx) | 👋 The first-run walkthrough. | 203 |
| [`SavedConfigsPanel.tsx`](SavedConfigsPanel.tsx) | 💾 Save and reload a backtest configuration. | 186 |
| [`onboarding-art.tsx`](onboarding-art.tsx) | 🎨 The drawings the walkthrough uses. | 151 |
| [`AuthGate.tsx`](AuthGate.tsx) | 🔐 Bounces an unauthenticated view to the sign-in page. | 125 |
| [`DeviationColorSettings.tsx`](DeviationColorSettings.tsx) | 🎨 Colour rules for VWAP deviation columns. | 119 |
| [`SourceMark.tsx`](SourceMark.tsx) | 📥 Which data source a run used. | 108 |
| [`StrategyMark.tsx`](StrategyMark.tsx) | 🧠 Which strategy a run used. | 107 |
| [`SchwabAuthWidget.tsx`](SchwabAuthWidget.tsx) | 🏦 The Schwab connect/refresh control. | 102 |
| [`ErrorBoundary.tsx`](ErrorBoundary.tsx) | 🧯 Catches a render crash and shows something other than a blank page. | 99 |
| [`VerifyEmailNotice.tsx`](VerifyEmailNotice.tsx) | ✉️ The "confirm your address" notice. | 98 |
| [`DayCountStepper.tsx`](DayCountStepper.tsx) | 📅 Day-range stepper. The ceiling depends on the interval — 180 days intraday, 7,305 for daily and weekly. | 95 |
| [`OfflineBanner.tsx`](OfflineBanner.tsx) | 📴 Says so when the browser loses the network. | 77 |
| [`SectionHeader.tsx`](SectionHeader.tsx) | 📑 The bar at the top of each Market Grid panel. | 61 |
| [`SymbolOption.tsx`](SymbolOption.tsx) | One row in the symbol dropdown. | 45 |
| [`StatusBanner.tsx`](StatusBanner.tsx) | ✅ The completion banner. | 28 |
| [`accessibility.a11y.test.tsx`](accessibility.a11y.test.tsx) | 🧪 axe-core over the shared components, plus the keyboard and screen-reader affordances. | 179 |
| [`IntervalPicker.a11y.test.tsx`](IntervalPicker.a11y.test.tsx) | 🧪 The interval popup measured with axe and driven from the keyboard. | 177 |
| [`SymbolMark.test.ts`](SymbolMark.test.ts) | Tests for `SymbolMark.tsx`. | 118 |


---

## 🗃 Subfolders

| Folder | ➜ What lives there |
|:--|:--|
| [`cards/`](cards) | 🃏 Stat, info and legend cards |
| [`charts/`](charts) | 📈 Plotly wrappers — candlestick, equity, P&L, Elliott Wave |
| [`motion/`](motion) | ✨ Shared animation helpers |
| [`tables/`](tables) | 📋 Trade log, patterns, optimiser |
| [`ui/`](ui) | 🧱 shadcn/ui primitives — button, input, slider, tabs, dialog |


---

## 💡 Worth knowing

- ➜ **The rule is a count, not a feeling:** used by two or more screens, it belongs here; used by one, it belongs in that feature folder.


---

<div align="center">

<sub>⬅ <a href="../../../README.md">Project README</a> · <a href="..">web/src/</a></sub>

</div>
