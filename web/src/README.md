<div align="center">

# ⚛️ Application Source

**Where the dashboard is actually built.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| ▶️ **Entry** | [`main.tsx`](main.tsx) ➜ [`App.tsx`](App.tsx) |
| 🎨 **All styling** | [`index.css`](index.css) — theme tokens live in the `.dark` block |
| 📐 **Layout rule** | Shared ➜ [`components/`](components) · page-specific ➜ [`features/`](features) · pure logic ➜ [`lib/`](lib) |
| 📁 **Path** | `web/src/` |
| 📦 **Holds** | `3` files · `1,912` lines · `5` subfolders |


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`App.tsx`](App.tsx) | 🧭 The shell: header, sidebar, and which page is showing. | 161 |
| [`index.css`](index.css) | 🎨 Theme tokens, the app background, and every shared class. | 1,732 |
| [`main.tsx`](main.tsx) | ▶️ Mounts React onto the page. | 19 |


---

## 🗃 Subfolders

| Folder | ➜ What lives there |
|:--|:--|
| [`assets/`](assets) | 🖼 Images the bundle imports |
| [`components/`](components) | 🎨 Shared UI used in more than one place |
| [`features/`](features) | 🖼 One folder per screen |
| [`lib/`](lib) | 🧩 Pure functions, all unit-tested |
| [`store/`](store) | 🗃 Client state (Zustand) |


---

## 💡 Worth knowing

- ➜ **Theme colours are tokens, not literals.** Change `.dark` in [`index.css`](index.css); do not hard-code a hex in a component.


---

<div align="center">

<sub>⬅ <a href="../../README.md">Project README</a> · <a href="..">web/</a></sub>

</div>
