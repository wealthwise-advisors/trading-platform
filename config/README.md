# ⚙️ `config`

**Settings and credential templates.**

> [!CAUTION]
> **`credentials.yaml` and `schwab_tokens.json` are gitignored and must never be
> committed.** Only the `.example` template belongs in version control. Five
> predecessor repositories hardcoded live credentials into source files; see
> [`legacy/REDACTIONS.md`](../legacy/REDACTIONS.md) for what that cost.

Copy the template and fill in your own values:

```bash
cp config/credentials.yaml.example config/credentials.yaml
```

`settings.yaml` holds non-secret configuration — contract specifications, session
hours, and which directory the CSV provider reads.

### Files in this directory

| File | Purpose | Lines |
|---|---|---:|
| [`settings.yaml`](settings.yaml) | Non-secret configuration: contract specifications, session hours, data directories. | 95 |
| [`credentials.yaml.example`](credentials.yaml.example) | AutoTrader — Credentials Template | 34 |

---

<sub>[⬅ Back to the project README](../README.md)</sub>
