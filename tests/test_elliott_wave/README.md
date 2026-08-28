<div align="center">

# 🌊 Elliott Wave Tests

**The rules are the specification. These hold them.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Covers** | [`src/analysis/elliott_wave`](../../src/analysis/elliott_wave) — all 13 modules |
| 📘 **Specification** | [`docs/ELLIOTT_WAVE_RULES.md`](../../docs/ELLIOTT_WAVE_RULES.md) |
| 🚨 **Route count** | [`test_pipeline_and_api.py`](test_pipeline_and_api.py) asserts an exact API route count — it fails on purpose when a route is added |
| 📁 **Path** | `tests/test_elliott_wave/` |
| 📦 **Holds** | `10` files · `2,509` lines |


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`test_guards.py`](test_guards.py) | 🚦 The rule gates. A structure that breaks a rule is not a wave. | 437 |
| [`test_pipeline_and_api.py`](test_pipeline_and_api.py) | ▶️ End-to-end pipeline, plus the API route-count guard. | 285 |
| [`test_structures.py`](test_structures.py) | 🧱 Every structure type enumerates correctly. | 274 |
| [`test_combination.py`](test_combination.py) | 🔗 W-X-Y and W-X-Y-X-Z. | 271 |
| [`test_impulse_rules.py`](test_impulse_rules.py) | 📈 The three impulse rules. | 241 |
| [`test_extension.py`](test_extension.py) | 📏 Extended waves. | 270 |
| [`test_triangle.py`](test_triangle.py) | 🔺 Contracting and expanding triangles. | 238 |
| [`test_flat_subtype.py`](test_flat_subtype.py) | ➖ Regular, expanded and running flats. | 200 |
| [`test_pivots.py`](test_pivots.py) | 📍 The pivot set everything is built from. | 161 |
| [`conftest.py`](conftest.py) | ⚙️ Shared fixtures and synthetic wave data. | 132 |


---

<div align="center">

<sub>⬅ <a href="../../README.md">Project README</a> · <a href="..">tests/</a></sub>

</div>
