<div align="center">

# ✨ Motion Primitives

**Shared animation, so timings cannot drift apart.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Does** | One place for durations and easings |
| 📐 **Rule** | Motion explains a change. It never loops for decoration |
| 📁 **Path** | `web/src/components/motion/` |
| 📦 **Holds** | `1` files · `102` lines |


---

## 🔄 How it fits together

```
   primitives.tsx ──► fade · slide · stagger ──► used by every screen

   one place for durations and easings, so two components
   cannot disagree about how fast "fast" is.

   ╳ motion explains a change. It never loops for decoration.
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`primitives.tsx`](primitives.tsx) | Fade, slide and stagger helpers. | 102 |


---

## 💡 Worth knowing

- ➜ **One place for durations and easings**, so two components cannot disagree about how fast "fast" is.
- ➜ **Motion explains a change.** Looping animation with nothing to explain is attention-seeking that never stops.


---

<div align="center">

<sub>⬅ <a href="../../../../README.md">Project README</a> · <a href="..">web/src/components/</a></sub>

</div>
