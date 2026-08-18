# Redacted credentials in `legacy/`

The files listed below arrived from the retired repositories with **live
credentials hardcoded in the source**. Each value was replaced with
`REDACTED__see_legacy_REDACTIONS_md` before anything was committed here. The code
is preserved; the secrets are not.

**No credential value is recorded anywhere in this repository, including in this
file.** Only the file path and the key name are listed.

## Why this mattered

The archive exists to make deleting the old repositories safe. Copying the code
verbatim would have made the exposure worse rather than neutral -- the same
credentials in one more place, and this time in the repository that is actually
deployed to production.

## Detection

A key name (`api_key`, `secret`, `app_key`, `client_secret`, `refresh_token`, ...)
followed by a quoted literal of at least 16 characters with Shannon entropy of at
least 3.2. Placeholders, `os.environ` lookups and template strings are excluded, so
this reports assignments of real-looking values rather than every mention of the
word "secret".

## These need rotating

Redacting a copy does not un-expose a credential. Everything below should be
treated as compromised and rotated at the provider. Until the old repositories are
deleted they still hold the real values, in their working tree and their history.

| File | Keys found |
|---|---|
| `Wealthwise/py_scripts/elliot_wave.py` | api_key, secret |
| `Wealthwise/py_scripts/elliot_wave_10min.py` | api_key, secret |
| `Wealthwise/py_scripts/elliot_wave_15min.py` | api_key, secret |
| `Wealthwise/py_scripts/elliot_wave_1h.py` | api_key, secret |
| `Wealthwise/py_scripts/elliot_wave_30min.py` | api_key, secret |
| `Wealthwise/py_scripts/elliot_wave_5min.py` | api_key, secret |
| `backtest/py_scripts/ew_backtest.py` | api_key, secret |
| `trading-strategy/strategy/swings_divergence/defs.py` | secret |
| `trading-web/wealth_wise_project/backend/backtesting_strategy_five.py` | api_key, secret |
| `trading-web/wealth_wise_project/backend/backtesting_strategy_four.py` | api_key, secret |
| `trading-web/wealth_wise_project/backend/backtesting_strategy_one.py` | api_key, secret |
| `trading-web/wealth_wise_project/backend/backtesting_strategy_three.py` | api_key, secret |
| `trading-web/wealth_wise_project/backend/backtesting_strategy_two.py` | api_key, secret |
| `trading-web/wealth_wise_project/backend/iron_beam_authenticator.py` | api_key |
| `trading-web/wealth_wise_project/backend/iron_beam_trading_bot_four.py` | api_key, secret |
| `trading-web/wealth_wise_project/backend/iron_beam_trading_bot_one.py` | api_key, secret |
| `trading-web/wealth_wise_project/backend/iron_beam_trading_bot_three.py` | api_key, secret |
| `trading-web/wealth_wise_project/backend/iron_beam_trading_bot_two.py` | api_key, secret |
| `trading-web/wealth_wise_project/backend/order_api.py` | api_key |
| `trading-web/wealth_wise_project/backend/rithmic_trading_bot_five.py` | api_key, secret |
| `trading-web/wealth_wise_project/backend/rithmic_trading_bot_three.py` | api_key, secret |
| `trading-web/wealth_wise_project_schwab/backend/backtesting_strategy_one.py` | api_key, secret |
| `trading-web/wealth_wise_project_schwab/backend/backtesting_strategy_three.py` | api_key, secret |
| `trading-web/wealth_wise_project_schwab/backend/backtesting_strategy_two.py` | api_key, secret |
| `trading-web/wealth_wise_project_schwab/backend/order_api.py` | api_key, secret |
| `trading-web/wealth_wise_project_schwab/backend/schwab_trading_bot_one.py` | api_key, secret |
| `trading-web/wealth_wise_project_schwab/backend/schwab_trading_bot_three.py` | api_key, secret |
| `trading-web/wealth_wise_project_schwab/backend/schwab_trading_bot_two.py` | api_key, secret |
| `trading-web/wealth_wise_replay_project/backend/backtesting_strategy_four.py` | api_key, secret |
| `trading-web/wealth_wise_replay_project/backend/backtesting_strategy_one.py` | api_key, secret |
| `trading-web/wealth_wise_replay_project/backend/backtesting_strategy_two.py` | api_key, secret |
| `trading-web/wealth_wise_replay_project/backend/iron_beam_authenticator.py` | api_key |
| `trading-web/wealth_wise_replay_project/backend/iron_beam_trading_bot_four.py` | api_key, secret |
| `trading-web/wealth_wise_replay_project/backend/iron_beam_trading_bot_one.py` | api_key, secret |
| `trading-web/wealth_wise_replay_project/backend/iron_beam_trading_bot_two.py` | api_key, secret |
| `trading-web/wealth_wise_replay_project/backend/order_api.py` | api_key |

**36 files affected.**
