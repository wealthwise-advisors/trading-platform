<div align="center">

# 💾 Backups & Monitoring

**What exists only on the instance, how it gets off it, and how you find out when it stops.**

![backup](https://img.shields.io/badge/backup-nightly-22c55e?style=flat-square)
![storage](https://img.shields.io/badge/S3-versioned%20%C2%B7%20encrypted-FF9900?style=flat-square&logo=amazons3&logoColor=white)
![auth](https://img.shields.io/badge/auth-IAM%20instance%20role-7c6cf5?style=flat-square)
![restore](https://img.shields.io/badge/restore-tested%20in%20CI-0ea5e9?style=flat-square)

</div>

---

## 📍 At a glance

|   |   |
|:--|:--|
| 🎯 **Protects** | Accounts, sessions, OAuth identities, saved backtests, and the two credential files |
| ⏰ **Runs** | 03:15 UTC daily, from cron on the EC2 host |
| 🔐 **Auth** | An **IAM instance role** — no long-lived keys on the box |
| 🧪 **Proven by** | [`tests/test_backup_restore.py`](../tests/test_backup_restore.py) — restores, then signs in |
| 💵 **Cost** | Cents per month. The database is ~172 KB |

---

## 🔄 How it fits together

```
   EC2 instance
   ┌──────────────────────────────────────────┐
   │  api container                           │
   │    /app/data/autotrader.db  ◄── WAL      │
   │           │                              │
   │           │ sqlite3 .backup()            │   ╳ never `cp` -- see below
   │           ▼                              │
   │    consistent snapshot                   │
   └───────────┼──────────────────────────────┘
               │  + config/credentials.yaml
               │  + config/schwab_tokens.json
               │  + MANIFEST.txt
               ▼
          tar + gzip
               │
               ▼  IAM instance role, SSE-AES256
        s3://<bucket>/autotrader/<stamp>.tar.gz
               │
               ▼
        head-object ──► size must match, or the run FAILS
```

---

## 🚨 Why not `cp`

The database runs in **WAL mode**. A plain file copy takes the main database
file and not the `-wal` sidecar, so anything committed but not yet checkpointed
is missing — and the copy opens without complaint.

This is demonstrated, not asserted. From
[`tests/test_backup_restore.py`](../tests/test_backup_restore.py):

```
   rows committed:          500
   a plain cp of the .db:   unreadable (OperationalError)
   sqlite online backup:    500
```

The naive copy did not merely lose rows — the `CREATE TABLE` was in the WAL too,
so the table did not exist in it at all.

---

## 🛠 One-time setup

### ◆ 1 · Create the bucket

Public access blocked, versioned, encrypted. **These are not optional
hardening** — the tarball contains live brokerage credentials, and they are what
makes putting it in S3 acceptable at all.

```bash
BUCKET=wealthwise-autotrader-backups        # must be globally unique
aws s3api create-bucket --bucket "$BUCKET" --region us-east-1

aws s3api put-public-access-block --bucket "$BUCKET" \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

aws s3api put-bucket-versioning --bucket "$BUCKET" \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption --bucket "$BUCKET" \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
```

> [!IMPORTANT]
> **Versioning is what protects you from the backup script itself.** If a bug
> ever uploaded an empty or truncated file over a good one, the previous version
> is still there. Without it, a bad backup silently replaces a good one.

### ◆ 2 · Create the IAM role and attach it to the instance

An **instance role**, not an access key. A key on the box is a credential that
can be stolen with the box; a role issues short-lived credentials that cannot be
copied off it.

`backup-policy.json` — scoped to this one prefix, and it **cannot delete
versions**:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:ListBucket"],
    "Resource": [
      "arn:aws:s3:::wealthwise-autotrader-backups",
      "arn:aws:s3:::wealthwise-autotrader-backups/autotrader/*"
    ]
  }]
}
```

```bash
aws iam create-role --role-name autotrader-backup \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}'

aws iam put-role-policy --role-name autotrader-backup \
  --policy-name s3-backup --policy-document file://backup-policy.json

aws iam create-instance-profile --instance-profile-name autotrader-backup
aws iam add-role-to-instance-profile \
  --instance-profile-name autotrader-backup --role-name autotrader-backup

aws ec2 associate-iam-instance-profile --instance-id <YOUR-INSTANCE-ID> \
  --iam-instance-profile Name=autotrader-backup
```

> [!NOTE]
> `s3:DeleteObject` is needed only for the retention step. Because versioning is
> on and the policy does **not** grant `s3:DeleteObjectVersion`, a delete leaves
> a delete-marker and the object is still recoverable.

### ◆ 3 · Schedule it

```bash
sudo tee /etc/cron.d/autotrader-backup >/dev/null <<'CRON'
BACKUP_BUCKET=wealthwise-autotrader-backups
15 3 * * * root /opt/wealthwise/repo/scripts/backup.sh >> /var/log/autotrader-backup.log 2>&1
CRON
```

Run it once by hand first, and read the output:

```bash
sudo BACKUP_BUCKET=wealthwise-autotrader-backups /opt/wealthwise/repo/scripts/backup.sh
```

---

## ♻️ Restoring

```bash
scripts/restore.sh --list                              # what is in the bucket
scripts/restore.sh --inspect 2026-08-29T03-15-00Z      # verify, change nothing
scripts/restore.sh --to /tmp/scratch 2026-08-29T03-15-00Z
scripts/restore.sh --production 2026-08-29T03-15-00Z   # asks for confirmation
```

| Mode | ➜ Does |
|:--|:--|
| `--list` | Lists every backup with size and date |
| `--inspect` | Downloads, verifies integrity, prints row counts. **Writes nothing** |
| `--to DIR` | Restores into a scratch directory you can point the API at |
| `--production` | Overwrites the live database. Requires typing `RESTORE`, and **snapshots the current database first** |

> [!TIP]
> Reading a backup and overwriting production are **different commands**, so
> reading one can never do the other by accident. `--production` also removes the
> stale `-wal` and `-shm` sidecars, which belong to the database being replaced —
> left behind, SQLite would try to apply them to the new file.

---

## 📡 Uptime monitoring — what to set up

**UptimeRobot free tier**: 50 monitors, 5-minute checks, email alerts.

### ◆ Monitor 1 — the API is genuinely alive

| Field | Value |
|:--|:--|
| **Type** | HTTP(s) |
| **URL** | `https://3-218-23-37.sslip.io/api/health` |
| **Interval** | 5 minutes |
| **Keyword** *(optional)* | `ok` — "exists" is weaker than "says it is healthy" |

> [!CAUTION]
> **Monitor `/api/health`, not `/`.**
>
> nginx serves the dashboard from static files. `/` returns **200 with a working
> page even when the API and the database are completely dead** — so a monitor on
> `/` would report green during exactly the outage you need to hear about.

### ◆ Monitor 2 — the certificate

Enable **SSL / certificate expiry monitoring** on the same monitor.

The Let's Encrypt certificate expires **18 November 2026**. certbot renews it
automatically, but a silent renewal failure breaks the site for everyone on a
date that is already known. This is the cheapest possible warning.

### ◆ Alerting

Add your email as an alert contact. Discord works too, via
**Settings ➜ Alert Contacts ➜ Webhook** with a Discord webhook URL.

---

## 💡 Worth knowing

- ➜ **A backup nobody restored is a guess.** [`tests/test_backup_restore.py`](../tests/test_backup_restore.py) restores a snapshot and **signs in to it over HTTP** on every CI run, so the mechanism cannot rot quietly.
- ➜ **The script refuses a snapshot with zero users.** That is a backup of the wrong file, and keeping it would let a good one age out of the retention window.
- ➜ **Upload success is verified, not assumed.** `head-object` must report the same byte count, or the run fails — the same reasoning as the deploy asking the server which commit it is serving.
- ➜ **Retention deletes only *after* the new object is confirmed present.** A prune that runs first is how you end up with nothing at all.
- ➜ **`credentials.yaml` and `schwab_tokens.json` are gitignored**, so they exist on that one box and nowhere else. They are the reason this backup covers more than the database.

---

<div align="center">
<sub>⬅ <a href="../README.md">Project README</a> · <a href=".">docs/</a></sub>
</div>
