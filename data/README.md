# 📈 `data`

**Bundled samples, and where downloads land.**

| Directory | Contents | In git? |
|---|---|---|
| [`sample/`](sample) | 5,000-row slices of 17 instruments | ✅ yes |
| `historical/` | Where fetched data is written | ❌ ignored |
| `live/` | Live session working files | ❌ ignored |

**The samples are real data, just short.** They are enough for the test suite and for
trying the app without credentials.

Full history — an 18-year 1-minute ES series among others — is far too large for an
ordinary repository and lives in
[`wealthwise-advisors/data`](https://github.com/wealthwise-advisors/data) via Git LFS.
A single file there is ~335 MB, and GitHub rejects anything over 100 MB.

### Subdirectories

| Directory | Files |
|---|---:|
| [`sample/`](sample) | 17 |

---

<sub>[⬅ Back to the project README](../README.md)</sub>
