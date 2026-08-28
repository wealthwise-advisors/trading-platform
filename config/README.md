<div align="center">

# ⚙️ Configuration & Credentials

**Settings that ship, and secrets that must never leave this machine.**

![secrets](https://img.shields.io/badge/secrets-gitignored-ef4444?style=flat-square) ![settings](https://img.shields.io/badge/settings-yaml-0ea5e9?style=flat-square)

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Does** | Holds every tunable, and the broker credentials |
| 🚨 **Never commit** | `credentials.yaml` · `schwab_tokens.json` — both gitignored, and they stay that way |
| ✅ **Safe to commit** | `settings.yaml` · `credentials.yaml.example` |
| 📁 **Path** | `config/` |
| 📦 **Holds** | `6` files · `219` lines |


---

## 🔄 How it fits together

```
   settings.yaml ────────► src/config.py ──► the whole app
   (committed, safe)

   credentials.yaml ─────┐
   schwab_tokens.json ───┴► gitignored ──► ╳ NEVER committed
                                            ╳ NEVER in an image
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`settings.yaml`](settings.yaml) | ⚙️ Data paths, session hours, defaults — read by [`src/config.py`](../src/config.py). | 138 |
| [`credentials.yaml.example`](credentials.yaml.example) | 📄 The template. Copy to `credentials.yaml` and fill in. | 34 |
| [`credentials.yaml`](credentials.yaml) | 🚨 **Secret.** Broker API keys. Gitignored. | 11 |
| [`schwab_tokens.json`](schwab_tokens.json) | 🚨 **Secret.** The live Schwab token pair. Gitignored, and it expires. | 12 |
| [`schwab_tokens.json.bak-11aug`](schwab_tokens.json.bak-11aug) | — | 12 |
| [`schwab_tokens.json.replaced-20260817-193849`](schwab_tokens.json.replaced-20260817-193849) | — | 12 |


---

## 💡 Worth knowing

- ➜ **On a 24-hour token-expiry warning, ask for a fresh token.** Do not re-run the auth flow unattended.
- ➜ **`.bak-*` and `.replaced-*` files are old token copies.** Just as secret as the live one — never commit them either.


---

<div align="center">

<sub>⬅ <a href="../README.md">Project README</a></sub>

</div>
