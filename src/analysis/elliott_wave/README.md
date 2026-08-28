<div align="center">

# 🌊 The Elliott Wave Engine

**Eight structures, three lifecycle stages, one pipeline.**

![modules](https://img.shields.io/badge/modules-13-7c6cf5?style=flat-square) ![structures](https://img.shields.io/badge/structures-8-0ea5e9?style=flat-square)

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Does** | Pivots ➜ candidate structures ➜ rule gates ➜ measurements |
| 🔄 **Lifecycle** | `ENUMERATED` ➜ `GATED` ➜ `MEASURED` |
| 📘 **Specification** | [`docs/ELLIOTT_WAVE_RULES.md`](../../../docs/ELLIOTT_WAVE_RULES.md) · [`ELLIOTT_WAVE_IMPLEMENTATION.md`](../../../docs/ELLIOTT_WAVE_IMPLEMENTATION.md) |
| 📦 **Holds** | `12` files · `2,267` lines |


---

## 🔄 How it fits together

```
   pivots.py ──► enumerate ──► validation.py ──► measurements.py
                    │            (the rules)       (ratios, targets)
        ┌───────────┼───────────┬───────────┐
        ▼           ▼           ▼           ▼
    impulse   correction   diagonal    triangle   ──► combination.py
                                                       hierarchy.py
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`pipeline.py`](pipeline.py) | ▶️ The entry point that runs the whole sequence. | 127 |
| [`pivots.py`](pivots.py) | The pivot set every structure is enumerated from. | 154 |
| [`validation.py`](validation.py) | 🚦 The rule gates. A structure that fails one is not a wave. | 204 |
| [`measurements.py`](measurements.py) | 📏 Fibonacci ratios, targets and projections. | 292 |
| [`impulse.py`](impulse.py) | 5-wave motive structures. | 231 |
| [`correction.py`](correction.py) | A-B-C corrective structures. | 194 |
| [`diagonal.py`](diagonal.py) | Leading and ending diagonals. | 238 |
| [`triangle.py`](triangle.py) | Contracting and expanding triangles. | 191 |
| [`combination.py`](combination.py) | W-X-Y and W-X-Y-X-Z combinations. | 263 |
| [`hierarchy.py`](hierarchy.py) | Degree nesting — a wave inside a wave. | 100 |
| [`momentum.py`](momentum.py) | Momentum confirmation for a candidate. | 92 |
| [`models.py`](models.py) | The dataclasses every module passes around. | 181 |


---

<div align="center">

<sub>⬅ <a href="../../../README.md">Project README</a> · <a href="..">src/analysis/</a></sub>

</div>
