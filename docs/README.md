<div align="center">

# 📚 Documentation

**The long-form references. Start with QUICKSTART.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🚀 **New here?** | [`QUICKSTART.md`](QUICKSTART.md) ➜ [`INSTALLATION.md`](INSTALLATION.md) ➜ [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md) |
| 🌊 **Elliott Wave** | [`ELLIOTT_WAVE.md`](ELLIOTT_WAVE.md) — one document, ~3,500 lines. The rules are the specification. |
| 📋 **Planning** | [`PRD.md`](PRD.md) ➜ [`Technical Requirements Document.md`](Technical%20Requirements%20Document.md) ➜ [`Design Document.md`](Design%20Document.md) ➜ [`Implementation Plan.md`](Implementation%20Plan.md) |
| 🔒 **Security** | [`SECURITY_AUDIT.md`](SECURITY_AUDIT.md) |
| 📁 **Path** | `docs/` |
| 📦 **Holds** | `18` files · `6,595` lines · `1` subfolders |


---

## 🔄 How it fits together

```
   new here ──► QUICKSTART ──► INSTALLATION ──► DEVELOPER_GUIDE
                                                      │
   going deeper ──► DESIGN DOCUMENT ──► API_GUIDE ───┤
                                                      ▼
   Elliott Wave ──► ELLIOTT_WAVE.md  (rules ─► requirements ─► architecture
                                       ─► implementation, one file)
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`QUICKSTART.md`](QUICKSTART.md) | 🚀 Running in five minutes. | 41 |
| [`INSTALLATION.md`](INSTALLATION.md) | 📦 Full setup, including Python 3.12. | 92 |
| [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md) | 🛠 How to work in this codebase. | 233 |
| [`Design Document.md`](Design%20Document.md) | 🏗 How the pieces fit. | 293 |
| [`ELLIOTT_WAVE.md`](ELLIOTT_WAVE.md) | 🌊 **The whole wave engine** — rules, requirements, architecture, build record. | 3,536 |
| [`CONFIGURATION.md`](CONFIGURATION.md) | ⚙️ Every setting explained. | 133 |
| [`API_GUIDE.md`](API_GUIDE.md) | 🔌 The endpoints. | 91 |
| [`ELLIOTT_WAVE.md`](ELLIOTT_WAVE.md#rules) | 🌊 **The specification.** Every rule a structure must satisfy. | 1,152 |
| [`ELLIOTT_WAVE.md`](ELLIOTT_WAVE.md#requirements) | 🌊 Requirements for the wave engine. | 1,251 |
| [`ELLIOTT_WAVE.md`](ELLIOTT_WAVE.md#architecture) | 🌊 How the 13 modules interlock. | 639 |
| [`ELLIOTT_WAVE.md`](ELLIOTT_WAVE.md#implementation) | 🌊 The build baseline. | 456 |
| [`Technical Requirements Document.md`](Technical%20Requirements%20Document.md) | 📋 System requirements. | 279 |
| [`PRD.md`](PRD.md) | 📋 Product requirements. | 169 |
| [`Implementation Plan.md`](Implementation%20Plan.md) | 📋 Phases, dependencies and what is left. | 221 |
| [`UI_UX.md`](UI_UX.md) | 🎨 Interface decisions. | 198 |
| [`SECURITY_AUDIT.md`](SECURITY_AUDIT.md) | 🔒 Findings and what was done. | 138 |
| [`RELEASE.md`](RELEASE.md#audit) | ✅ Pre-release checks. | 320 |
| [`RELEASE.md`](RELEASE.md) | 📝 What shipped, and the checks behind it. | 435 |
| [`BETA_TESTING.md`](BETA_TESTING.md) | 🧪 Test accounts, critical flows, bug reporting. | 174 |
| [`RELEASE.md`](RELEASE.md#notes) | 📝 What changed. | 93 |
| [`VERIFICATION_REPORT.md`](VERIFICATION_REPORT.md) | 🔬 Correctness evidence. | 235 |
| [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) | 🔧 When it will not start. | 63 |
| [`FAQ.md`](FAQ.md) | ❓ Short answers. | 22 |


---

## 🗃 Subfolders

| Folder | ➜ What lives there |
|:--|:--|
| [`assets/`](assets) | 🖼 Images the documents embed |


---

## 💡 Worth knowing

- ➜ **[`ELLIOTT_WAVE.md`](ELLIOTT_WAVE.md#rules) is a specification, not a description.** [`tests/test_elliott_wave/test_guards.py`](../tests/test_elliott_wave/test_guards.py) enforces it.
- ➜ **Every folder has its own README too**, so orientation is available where you are rather than only here.


---

<div align="center">

<sub>⬅ <a href="../README.md">Project README</a></sub>

</div>
