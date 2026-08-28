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
| 📦 **Holds** | `13` files · `1,593` lines · `5` subfolders |


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`SymbolMark.tsx`](SymbolMark.tsx) | 🏷 The instrument badge. Each contract keeps its own identity colour. | 414 |
| [`InstrumentPicker.tsx`](InstrumentPicker.tsx) | 🔍 Searchable symbol chooser. | 253 |
| [`AuthGate.tsx`](AuthGate.tsx) | 🔐 Bounces an unauthenticated view to the sign-in page. | 86 |
| [`SchwabAuthWidget.tsx`](SchwabAuthWidget.tsx) | 🏦 The Schwab connect/refresh control. | 102 |
| [`DeviationColorSettings.tsx`](DeviationColorSettings.tsx) | 🎨 Colour rules for VWAP deviation columns. | 119 |
| [`SourceMark.tsx`](SourceMark.tsx) | 📥 Which data source a run used. | 108 |
| [`StrategyMark.tsx`](StrategyMark.tsx) | 🧠 Which strategy a run used. | 107 |
| [`DayCountStepper.tsx`](DayCountStepper.tsx) | 📅 Day-range stepper. | 86 |
| [`SectionHeader.tsx`](SectionHeader.tsx) | 📑 The bar at the top of each Market Grid panel. | 61 |
| [`SavedConfigsPanel.tsx`](SavedConfigsPanel.tsx) | 💾 Save and reload a backtest configuration. | 66 |
| [`StatusBanner.tsx`](StatusBanner.tsx) | ✅ The completion banner. | 28 |
| [`SymbolOption.tsx`](SymbolOption.tsx) | One row in the symbol dropdown. | 45 |
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

<div align="center">

<sub>⬅ <a href="../../../README.md">Project README</a> · <a href="..">web/src/</a></sub>

</div>
