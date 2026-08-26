# Configuration

## `config/settings.yaml` (committed, no secrets)

App name/version/logging, backtesting defaults (capital, commission,
slippage), and per-symbol contract specs (tick size/value, margins).
Loaded via `src.config.load_config()`, which the API uses on startup and
checks for the required `app`/`backtesting`/`contracts` sections.

### How `config/` is located

`src.data.schwab_provider.py` and `external_csv_provider.py` (the two
providers that read `config/` directly) use
`src.config.resolve_config_dir()`, checked in order:

1. `AUTOTRADER_CONFIG_DIR` env var, if set — explicit override, always wins.
2. `<current working directory>/config` — correct for `uvicorn
   api.main:app` run from the repo root (the documented dev workflow)
   and for the Docker image (`WORKDIR /app`, `config/` bind-mounted at
   `/app/config`, cwd is `/app` at container startup).
3. A package-relative fallback (two directories up from `src/config.py`)
   for editable installs.

Task 10.1 verification found the two providers originally hardcoded only
the package-relative form, which resolves correctly for `pip install -e .`
(where `__file__` still points at the repo) but silently pointed outside
any real `config/` directory under a true `pip install .` or the built
Docker image (both install into `site-packages`). Fixed by routing both
through the shared, multi-candidate `resolve_config_dir()` above.

## `config/credentials.yaml` (gitignored, never commit)

```bash
cp config/credentials.yaml.example config/credentials.yaml
```

Only needed for Schwab or Rithmic — synthetic data, your own CSVs,
backtesting, and replay all work without it.

### Schwab (live/recent historical data)

1. Create an app at [developer.schwab.com](https://developer.schwab.com),
   callback URL `https://127.0.0.1`.
2. Fill in `credentials.yaml`:
   ```yaml
   schwab:
     app_key: "YOUR_32_CHAR_APP_KEY"
     app_secret: "YOUR_16_CHAR_SECRET"
     callback_url: "https://127.0.0.1"
     tokens_file: "config/schwab_tokens.json"
   ```
3. In the UI, select **Live Data (Schwab)** and follow the auth widget
   (opens Schwab's login page, paste the redirect URL back). Writes
   `config/schwab_tokens.json` (gitignored).
4. The access token (30 min) refreshes automatically in the background.
   The refresh token lasts 7 days; the sidebar warns 24h before expiry —
   re-auth by clicking the link again, same as step 3.

### Rithmic (real historical + live data)

Requires a licensed Rithmic account. Either:

```yaml
rithmic:
  credentials_path: "/path/to/your/rithmic/credentials"   # dir containing RITHMIC_LIVE.ini
```

or set `RITHMIC_CREDENTIALS_PATH` as an environment variable / in a root
`.env` file — either mechanism works, `src/data/rithmic_provider.py`
checks both.

## Environment variables

See [.env.example](../.env.example) for the full list with explanations.
Summary:

| Variable | Default | Purpose |
|---|---|---|
| `AUTOTRADER_CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Comma-separated origins the API accepts browser requests from |
| `AUTOTRADER_CONFIG_DIR` | (unset) | Explicit override for where `config/` lives |
| `AUTOTRADER_DB_PATH` | `data/autotrader.db` | SQLite file |
| `AUTOTRADER_COMMIT` | `unknown` | Deployed commit SHA, surfaced by `/api/version` |
| `AUTOTRADER_INSECURE_COOKIE` | (unset) | `1` drops the `Secure` flag on the session cookie. **Local `http://` only** |
| `RITHMIC_CREDENTIALS_PATH` | (unset) | Alternative to `credentials.yaml`'s `rithmic.credentials_path` |

Schwab credentials are **not** read from environment variables — the
underlying `schwabdev` client needs a token *file* it can read/write
across restarts, which doesn't fit an env-var model.

### OAuth sign-in

Google, LinkedIn and Twitter/X sign-in. All default to empty, and empty is a
supported state: the provider reports itself as unconfigured and its button on
the sign-in page says so, rather than failing silently.

| Variable | Purpose |
|---|---|
| `AUTOTRADER_PUBLIC_BASE_URL` | The public origin browsers reach this deployment on, no trailing slash. Required — the redirect URI is built from it |
| `AUTOTRADER_GOOGLE_CLIENT_ID` / `_SECRET` | From the Google Cloud console, OAuth 2.0 Client ID of type *Web application* |
| `AUTOTRADER_LINKEDIN_CLIENT_ID` / `_SECRET` | From LinkedIn Developers, with the *Sign In with LinkedIn using OpenID Connect* product added |
| `AUTOTRADER_TWITTER_CLIENT_ID` / `_SECRET` | From the X developer portal, an OAuth 2.0 **Confidential** client |

Register this redirect URI at each provider, exactly:

```text
{AUTOTRADER_PUBLIC_BASE_URL}/api/auth/oauth/{google|linkedin|twitter}/callback
```

`py -3.12 scripts/manage_users.py oauth-status` prints which are configured and
the exact URI for each, so there is no need to assemble it by hand.

**OAuth never creates an account.** It is a second door into an account that
already exists. Google and LinkedIn link themselves on first use by matching a
*verified* email to an existing user; an unverified or unknown address is
refused. Twitter/X returns no email at any scope, so it has nothing to match on
and must be linked by hand:

```powershell
py -3.12 scripts/manage_users.py link akash --provider twitter --subject <id>
```

**Apple is not implemented.** "Sign in with Apple" needs a paid Apple Developer
Program membership and uses an ES256-signed JWT built from a `.p8` key instead
of a client secret, plus a cross-site `form_post` callback. The button stays on
the "not connected yet" notice until that account exists; see the module
docstring in `api/oauth.py` for what adding it would involve.

## Docker

`docker-compose.yml` mounts `config/` read-only into the API container and
sets `AUTOTRADER_CORS_ORIGINS` to the nginx-served frontend's origin. Copy
`credentials.yaml` onto the host before `docker compose up` if you need
Schwab/Rithmic.
