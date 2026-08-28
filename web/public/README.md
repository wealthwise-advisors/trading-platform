<div align="center">

# 📄 Static Pages & Fonts

**Copied into the build verbatim. These pages never load the app's CSS.**

![copied](https://img.shields.io/badge/copied-verbatim-0ea5e9?style=flat-square) ![self----contained](https://img.shields.io/badge/self----contained-yes-22c55e?style=flat-square)

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Holds** | The sign-in journey and the legal pages |
| 🔒 **Self-contained** | Styles are inline, so app theming **cannot** change them |
| ⚠️ **Also on the Desktop** | [`scripts/run_local.py`](../../scripts/run_local.py) prefers the Desktop copies — edit both, or the local rig shows a stale page |
| 📁 **Path** | `web/public/` |
| 📦 **Holds** | `9` files · `5,023` lines |


---

## 🔄 How it fits together

```
   web/public/*  ──copied VERBATIM──►  web/dist/*  ──► nginx

   these pages never load index.css. Styles are inline, so
   app theming cannot reach them -- and cannot break them.

   ⚠️ run_local.py prefers the DESKTOP copies of the sign-in pages.
      Edit both, or the local rig shows you a stale page.
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`autotrader_signin.html`](autotrader_signin.html) | 🔐 Sign in · forgot password · reset password. | 1,032 |
| [`autotrader_signup.html`](autotrader_signup.html) | 📝 Create an account. | 1,109 |
| [`terms.html`](terms.html) | 📜 Terms of Service. | 159 |
| [`privacy.html`](privacy.html) | 🔏 Privacy Policy. | 167 |
| [`help.html`](help.html) | 💬 Help Center. | 135 |
| [`trading-office.jpg`](trading-office.jpg) | 🌃 The photograph behind the sign-in card. | 1,786 |
| [`TwemojiCountryFlags.woff2`](TwemojiCountryFlags.woff2) | 🏳 Flag font for the 234-country picker. | 610 |
| [`icons.svg`](icons.svg) | Sprite sheet. | 24 |
| [`favicon.svg`](favicon.svg) | Tab icon. | 1 |


---

## 💡 Worth knowing

- ➜ **These are the only pages a signed-out visitor sees.** A mistake here is the first thing anyone notices.


---

<div align="center">

<sub>⬅ <a href="../../README.md">Project README</a> · <a href="..">web/</a></sub>

</div>
