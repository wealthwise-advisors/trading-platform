<div align="center">

# 🖥 The Web Frontend

**React + TypeScript, built by Vite, served by nginx.**

![React](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=white) ![TypeScript](https://img.shields.io/badge/TypeScript-strict-3178C6?style=flat-square&logo=typescript&logoColor=white) ![Vite](https://img.shields.io/badge/Vite-build-646CFF?style=flat-square&logo=vite&logoColor=white) ![nginx](https://img.shields.io/badge/nginx-serve-009639?style=flat-square&logo=nginx&logoColor=white)

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| ▶️ **Dev** | `npm run dev` ➜ proxies `/api/*` to the backend |
| 📦 **Build** | `npm run build` ➜ `dist/` |
| 🎨 **Theme** | Graphite + violet-blue. Warm colours are reserved for **meaning** — red for a loss |
| 📄 **`public/` is copied verbatim** | The sign-in pages live there and never load `index.css` |
| 📦 **Holds** | `9` files · `495` lines · `2` subfolders |


---

## 🔄 How it fits together

```
   src/ ──► vite build ──► dist/ ──┐
                                   ├──► nginx ──► browser
   public/ ─── copied verbatim ────┘     │
   (sign-in, sign-up, terms, privacy)    └── /api/* ──► FastAPI
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`nginx.conf`](nginx.conf) | 🌐 Port 80. **Changes here must also go in `ssl.conf.template`.** | 152 |
| [`ssl.conf.template`](ssl.conf.template) | 🔒 Port 443 — a **separate** server block, hence the warning above. | 88 |
| [`Dockerfile`](Dockerfile) | 🐳 Builds the static bundle and the nginx image. | 31 |
| [`40-enable-ssl.sh`](40-enable-ssl.sh) | 🔑 Turns on TLS at container start. | 89 |
| [`vite.config.ts`](vite.config.ts) | ⚡ Build and dev-proxy config. | 26 |
| [`vitest.config.ts`](vitest.config.ts) | 🧪 Frontend test config. | 23 |
| [`package.json`](package.json) | 📦 Dependencies and scripts. | 47 |
| [`index.html`](index.html) | The SPA shell. | 14 |
| [`components.json`](components.json) | shadcn/ui generator config. | 25 |


---

## 🗃 Subfolders

| Folder | ➜ What lives there |
|:--|:--|
| [`public/`](public) | 📄 Copied verbatim — sign-in, sign-up, terms, privacy, help |
| [`src/`](src) | ⚛️ The application source |


---

## 💡 Worth knowing

- ➜ **nginx is configured twice.** Port 80 and port 443 are separate blocks — a fix applied to one only is a fix that works over `http` and not `https`.
- ➜ **`public/` never sees the app's CSS.** Those pages are self-contained, so app styling cannot change them.


---

<div align="center">

<sub>⬅ <a href="../README.md">Project README</a></sub>

</div>
