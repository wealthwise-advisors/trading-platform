<div align="center">

# 🧩 Frontend Logic & Helpers

**The pure functions. Every one of them is unit-tested.**

![vitest](https://img.shields.io/badge/vitest-unit-6E9F18?style=flat-square&logo=vitest&logoColor=white)

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Rule** | No JSX here. If it renders, it is a component |
| 🧪 **Testing** | Each `X.ts` has an `X.test.ts` beside it |
| ⚠️ **`types.ts` is a mirror** | It must match [`api/schemas`](../../../api/schemas) or the UI drops fields silently |
| 📁 **Path** | `web/src/lib/` |
| 📦 **Holds** | `30` files · `4,379` lines |


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`api.ts`](api.ts) | 🔌 Every call to the backend, in one module. | 168 |
| [`types.ts`](types.ts) | 📋 Mirrors [`api/schemas`](../../../api/schemas). Change one, change the other. | 474 |
| [`followLive.ts`](followLive.ts) | 📡 Keeps asking for bars that formed since the replay caught up. | 288 |
| [`deviationColors.ts`](deviationColors.ts) | 🎨 Colours a VWAP deviation column by the whole number it lands on. | 191 |
| [`volumeProfile.ts`](volumeProfile.ts) | 📊 Volume Profile, computed in the browser. | 216 |
| [`clock.ts`](clock.ts) | 🕐 Pure clock arithmetic for the time field. | 140 |
| [`resample.ts`](resample.ts) | ⏱ Display-only aggregation into wider candles. | 112 |
| [`dayRange.ts`](dayRange.ts) | 📅 Day counting over an inclusive date range. | 111 |
| [`rangebreaks.ts`](rangebreaks.ts) | ✂️ Hides non-trading hours so candles sit flush. | 57 |
| [`isoTime.ts`](isoTime.ts) | 🕰 ISO timestamp helpers. | 36 |
| [`priceFormat.ts`](priceFormat.ts) | 💲 Per-instrument decimal places. | 35 |
| [`insights.ts`](insights.ts) | 💡 Rule-based summary lines — no LLM. | 50 |
| [`savedConfigs.ts`](savedConfigs.ts) | 💾 Reads and writes saved configurations. | 39 |
| [`bandAgreement.ts`](bandAgreement.ts) | 📏 Do the bands agree across timeframes? | 67 |
| [`deviationColorSettings.ts`](deviationColorSettings.ts) | ⚙️ Persisted colour preferences. | 87 |
| [`volumeProfileShapes.ts`](volumeProfileShapes.ts) | 📊 Shapes the profile draws. | 80 |
| [`utils.ts`](utils.ts) | 🧰 Small shared helpers. | 6 |
| [`bandAgreement.test.ts`](bandAgreement.test.ts) | 🧪 Tests for [`bandAgreement.ts`](bandAgreement.ts). | 96 |
| [`chartAxis.test.ts`](chartAxis.test.ts) | 🧪 Tests for `chartAxis` — the helper it covers lives inside its caller, so there is no `chartAxis.ts` to link. | 145 |
| [`clock.test.ts`](clock.test.ts) | 🧪 Tests for [`clock.ts`](clock.ts). | 77 |
| [`dayRange.test.ts`](dayRange.test.ts) | 🧪 Tests for [`dayRange.ts`](dayRange.ts). | 221 |
| [`deviationColorSettings.test.ts`](deviationColorSettings.test.ts) | 🧪 Tests for [`deviationColorSettings.ts`](deviationColorSettings.ts). | 118 |
| [`deviationColors.test.ts`](deviationColors.test.ts) | 🧪 Tests for [`deviationColors.ts`](deviationColors.ts). | 468 |
| [`followLive.test.ts`](followLive.test.ts) | 🧪 Tests for [`followLive.ts`](followLive.ts). | 402 |
| [`isoTime.test.ts`](isoTime.test.ts) | 🧪 Tests for [`isoTime.ts`](isoTime.ts). | 94 |
| [`nowEastern.test.ts`](nowEastern.test.ts) | 🧪 Tests for `nowEastern` — the helper it covers lives inside its caller, so there is no `nowEastern.ts` to link. | 101 |
| [`priceFormat.test.ts`](priceFormat.test.ts) | 🧪 Tests for [`priceFormat.ts`](priceFormat.ts). | 56 |
| [`rangebreaks.test.ts`](rangebreaks.test.ts) | 🧪 Tests for [`rangebreaks.ts`](rangebreaks.ts). | 88 |
| [`resample.test.ts`](resample.test.ts) | 🧪 Tests for [`resample.ts`](resample.ts). | 234 |
| [`volumeProfileShapes.test.ts`](volumeProfileShapes.test.ts) | 🧪 Tests for [`volumeProfileShapes.ts`](volumeProfileShapes.ts). | 122 |


---

<div align="center">

<sub>⬅ <a href="../../../README.md">Project README</a> · <a href="..">web/src/</a></sub>

</div>
