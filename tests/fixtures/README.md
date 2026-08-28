<div align="center">

# 📎 Test Fixtures

**Real bars, pinned. Not generated at test time.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Why pinned** | Parity tests compare against bars the reference platform actually printed |
| 🚫 **Do not regenerate** | Rewriting these makes the tests agree with whatever the code now does |
| 📁 **Path** | `tests/fixtures/` |
| 📦 **Holds** | `1` files · `2,761` lines |


---

## 🔄 How it fits together

```
   the reference platform printed these bars
        │
        ▼
   es_1m_2026_08_12_13.csv  ──► test_reference_platform_parity.py

   ╳ do not regenerate. Rewriting a baseline makes the test agree
     with whatever the code now does, which is not a test.
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`es_1m_2026_08_12_13.csv`](es_1m_2026_08_12_13.csv) | 📈 /ES 1-minute bars, 12–13 Aug 2026 — the parity baseline. | 2,761 |


---

## 💡 Worth knowing

- ➜ **Pinned, not generated.** Parity tests compare against bars a reference platform actually printed — regenerating them would make the test agree with whatever the code now does.


---

<div align="center">

<sub>⬅ <a href="../../README.md">Project README</a> · <a href="..">tests/</a></sub>

</div>
