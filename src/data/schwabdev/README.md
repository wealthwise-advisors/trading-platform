<div align="center">

# 📦 schwabdev (vendored)

**Third-party Schwab SDK, copied in. Not our code.**

![vendored](https://img.shields.io/badge/vendored-third----party-f59e0b?style=flat-square) ![licence](https://img.shields.io/badge/licence-see%20LICENSE.txt-0ea5e9?style=flat-square)

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **What it is** | The [`schwabdev`](https://github.com/tylerebowers/Schwabdev) client, vendored into this repo |
| 🤔 **Why vendored** | It is not declared as a dependency, so the build cannot fetch it |
| 🚫 **Do not edit** | Local changes are lost on any update, and diverge silently from upstream |
| 📄 **Licence** | [`LICENSE.txt`](LICENSE.txt) — upstream's terms, not ours |
| 📁 **Path** | `src/data/schwabdev/` |
| 📦 **Holds** | `3` files · `930` lines |


---

## 🔄 How it fits together

```
   src/data/schwab_provider.py
        │  uses
        ▼
   schwabdev/  ◄── vendored copy of a third-party SDK
        │
        └── ╳ do not edit. Local changes diverge from upstream in silence.
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`api.py`](api.py) | The Schwab REST client. | 728 |
| [`stream.py`](stream.py) | The streaming client. | 181 |
| [`LICENSE.txt`](LICENSE.txt) | 📄 Upstream licence. Keep it with the code. | 21 |


---

## 💡 Worth knowing

- ➜ **Vendored, not a dependency.** It is copied in because the build cannot fetch it — which also means no automated update will ever touch it.
- ➜ **Keep [`LICENSE.txt`](LICENSE.txt) beside the code.** It is upstream's licence, and removing it would strip the terms the code is used under.


---

<div align="center">

<sub>⬅ <a href="../../../README.md">Project README</a> · <a href="..">src/data/</a></sub>

</div>
