<div align="center">

# 📄 Static Pages & Fonts

**Copied into the build verbatim. These pages never load the app's CSS.**

![copied](https://img.shields.io/badge/copied-verbatim-0ea5e9?style=flat-square) ![self----contained](https://img.shields.io/badge/self----contained-yes-22c55e?style=flat-square)

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Holds** | The legal pages, help, and the 404 page |
| 🔒 **Self-contained** | Styles are inline, so app theming **cannot** change them |
| 📁 **Path** | `web/public/` |
| 📦 **Holds** | `11` files · `639` lines of HTML |


---

## 🔄 How it fits together

```
   web/public/*  ──copied VERBATIM──►  web/dist/*  ──► nginx

   these pages never load index.css. Styles are inline, so
   app theming cannot reach them -- and cannot break them.
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`terms.html`](terms.html) | 📜 Terms of Service. | 169 |
| [`privacy.html`](privacy.html) | 🔏 Privacy Policy. | 196 |
| [`help.html`](help.html) | 💬 Help Center. | 193 |
| [`icons.svg`](icons.svg) | Sprite sheet. | 24 |
| [`favicon.svg`](favicon.svg) | Tab icon. | 1 |


---

## 💡 Worth knowing

- ➜ **There is no sign-in page any more** (removed 2026-10-16). The link opens the app directly; the old sign-in and sign-up addresses redirect to it.


---

<div align="center">

<sub>⬅ <a href="../../README.md">Project README</a> · <a href="..">web</a></sub>

</div>
