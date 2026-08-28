<div align="center">

# 🖼 Bundled Images

**Imported by the code, hashed by the build.**

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Holds** | Brand marks and the app background |
| 📦 **Versus [`public/`](../../public)** | These are **imported**, so Vite hashes and inlines them. `public/` is copied verbatim |
| 📁 **Path** | `web/src/assets/` |
| 📦 **Holds** | `6` files · `3,128` lines |


---

## 🔄 How it fits together

```
   import bg from "@/assets/app-background.jpg"
        │
        ▼  Vite hashes it, inlines the small ones
   dist/assets/app-background-a1b2c3.jpg

   vs web/public/ ──► copied verbatim, keeps its name, never hashed
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`app-background.jpg`](app-background.jpg) | 🌅 The golden trading-floor background behind the app. | 2,479 |
| [`brand-mark.png`](brand-mark.png) | 🔶 The AutoTrader mark. | 107 |
| [`brand-wordmark.png`](brand-wordmark.png) | 🔤 The wordmark beside it. | 392 |
| [`brand-favicon.png`](brand-favicon.png) | 🔖 Tab icon. | 51 |
| [`hero.png`](hero.png) | 🖼 Hero image. | 98 |
| [`vite.svg`](vite.svg) | Vite's default logo. | 1 |


---

## 💡 Worth knowing

- ➜ **Imported, so Vite hashes them** — a changed image gets a new filename and cannot be served stale from a cache. Files in [`public/`](../../public) keep their names and do not get this.


---

<div align="center">

<sub>⬅ <a href="../../../README.md">Project README</a> · <a href="..">web/src/</a></sub>

</div>
