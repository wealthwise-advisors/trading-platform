# Cloud — AutoTrader

Everything about where AutoTrader runs and how it gets there.

> **These are reference copies.** The files that actually run live in the
> GitHub repository `wealthwise-advisors/trading-platform`. Editing anything
> in this folder changes nothing — see *Making a change* at the bottom.

---

## What the cloud setup is

| | |
|---|---|
| **Provider** | AWS |
| **Service** | EC2 — a single `t3.micro` instance |
| **Region** | `us-east-1` |
| **Public address** | http://3.218.23.37 |
| **Runtime** | Docker Compose — two containers |
| **CI/CD** | GitHub Actions |
| **Path on the server** | `/opt/wealthwise/repo` |

---

## The two containers

```
   browser  →  :80  ┌─────────────────────┐
                    │  web                │   nginx 1.27-alpine
                    │  autotrader-web     │   serves the built React app
                    └──────────┬──────────┘   and proxies /api
                               │
                    ┌──────────┴──────────┐
                    │  api                │   python 3.12-slim
                    │  autotrader-api     │   FastAPI + uvicorn
                    └─────────────────────┘   healthcheck on /api/health
```

The API container has **no published port** — only the web container is
reachable from outside, and it proxies `/api` internally. One origin, so the
browser never makes a cross-origin request.

Two named volumes persist across deploys: `autotrader-data`, `autotrader-logs`.

Both containers are `restart: unless-stopped`, so they come back after a
reboot without anyone logging in.

---

## How a deploy happens

Triggered by a **push to `main`**. Nothing is deployed from a laptop.

```
push to main
     │
     ▼
1  correctness gate         two test suites must pass, or the server is never touched
     │
     ▼
2  resolve runner IP        checkip.amazonaws.com
     │
     ▼
3  open SSH                 aws ec2 authorize-security-group-ingress, that IP only, /32
     │
     ▼
4  ssh to EC2               git fetch --depth 1 && reset --hard origin/main
     │                      docker compose up --build -d
     │                      docker image prune -f
     ▼
5  health check             poll /api/health until 200, up to 150s
     │
     ▼
6  smoke test               dashboard serves <title>AutoTrader</title>
     │                      /api/strategies returns rsi_divergence
     ▼
7  close SSH                revoke the rule — runs even if an earlier step failed
```

Typical run: **~2m 30s**, of which the gate is ~2m 20s and the deploy itself
about 15 seconds.

---

## Two deliberate design choices

**Port 22 is never open between deploys.** GitHub runners get addresses from
thousands of ranges, far past the 60-rule limit on a security group, so they
cannot be allowlisted in advance. The workflow opens the single runner IP for
the length of the run and revokes it in an `always()` step.

**The server pulls with `--depth 1`.** Not for speed. An old commit in this
repository's history contains live Schwab OAuth tokens — removed since, but
still reachable in a full clone. A shallow fetch never retrieves those blobs.

---

## AWS permissions

The workflow uses an IAM user, `wealthwise-ci`, whose entire policy is:

- `ec2:AuthorizeSecurityGroupIngress`
- `ec2:RevokeSecurityGroupIngress`
- `ec2:DescribeSecurityGroups`

all scoped to one security group. It cannot see or touch the instance —
`ec2:DescribeInstances` and `ec2:TerminateInstances` both return `AccessDenied`.

**Secrets** live in GitHub Actions secrets, never in a file:
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `EC2_SG_ID`, `EC2_HOST`,
`EC2_SSH_KEY`.

---

## What is in this folder

```
cloud/
├── README.md              this file
├── workflows/
│   ├── deploy.yml         the AWS deploy pipeline
│   └── ci.yml             lint · types · tests · security audit · frontend
└── docker/
    ├── docker-compose.yml the two-container topology
    ├── api.Dockerfile     python:3.12-slim
    └── web.Dockerfile     node:22-slim build → nginx:1.27-alpine
```

---

## Checking on it

```bash
curl http://3.218.23.37/api/health          # expect 200
curl http://3.218.23.37/api/version         # {"version":"1.0.0","api":"autotrader"}
gh run list --workflow=Deploy --limit 5     # recent deploys
```

---

## Making a change

These copies are for reading. To change what actually deploys, edit the file
in the repository and push:

| To change | Edit in the repo |
|---|---|
| the deploy pipeline | `.github/workflows/deploy.yml` |
| CI checks | `.github/workflows/ci.yml` |
| container topology | `trading-platform/docker-compose.yml` |
| the API image | `trading-platform/Dockerfile` |
| the web image | `trading-platform/web/Dockerfile` |

GitHub Actions only reads workflows from `.github/workflows/` at the
**repository root** — a copy anywhere else is inert.
