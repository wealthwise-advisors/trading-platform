<div align="center">

# 🗄 The Database

**SQLite. Every account, session and saved backtest.**

![SQLite](https://img.shields.io/badge/SQLite-WAL-003B57?style=flat-square&logo=sqlite&logoColor=white) ![passwords](https://img.shields.io/badge/passwords-argon2id-7c6cf5?style=flat-square) ![tokens](https://img.shields.io/badge/tokens-SHA----256-22c55e?style=flat-square)

</div>

---


## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Does** | Persists results and people, behind a small module boundary |
| 🔑 **Never stores a secret in the clear** | Passwords are argon2id; sessions and links are stored as their SHA-256 |
| 📐 **Rule** | No repository function takes a default `user_id` — a forgotten argument is a `TypeError`, not a leak |
| 📁 **Path** | `db/` |
| 📦 **Holds** | `4` files · `1,409` lines |


---

## 🔄 How it fits together

```
   users ─┬─► sessions          SHA-256 of the cookie, never the cookie
          ├─► oauth_identities  matched on the provider's permanent subject
          ├─► email_tokens      confirm · reset · reminder, single-use
          └─► backtests ──► trades · equity · patterns · waves
                  ▲
                  └── every row carries user_id. That is the isolation.
```


---

## 📂 Files

| File | ➜ What it does | Lines |
|:--|:--|--:|
| [`users.py`](users.py) | 👥 Accounts, sessions, OAuth identities and email tokens — everything about **people**. | 601 |
| [`schema.sql`](schema.sql) | 🧱 The tables. Every statement is `IF NOT EXISTS`, so applying it is idempotent. | 309 |
| [`connection.py`](connection.py) | 🔌 Opening the file, the PRAGMAs, and applying + versioning the schema. | 236 |
| [`backtests.py`](backtests.py) | 📊 The only module that knows the backtest table layout. | 263 |


---

## 💡 Worth knowing

- ➜ **`IF NOT EXISTS` adds tables for free but never COLUMNS.** A new column needs an explicit `ALTER TABLE`, and it must run **before** `executescript`, because the script builds indexes on it.
- ➜ **The unique email index is partial** — `WHERE email != ''` — so accounts with no address are allowed. X sign-ins rely on exactly that.
- ➜ **Another user's row is `404`, never `403`.** A 403 would confirm the id exists.


---

<div align="center">

<sub>⬅ <a href="../README.md">Project README</a></sub>

</div>
