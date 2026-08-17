"""How the pasted Schwab redirect URL is turned into an auth code.

The previous implementation sliced between "code=" and a literal "%40".
Schwab's codes end with "@", which the address bar shows percent-encoded --
but several browsers copy the DECODED form, and that raised
"Could not parse auth code from the URL", which reads as a Schwab or network
problem rather than string handling. These tests pin every paste shape that
reaches the field.

complete_auth() is exercised with the network call stubbed: the parsing is what
is under test, not the token exchange.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.data.schwab_provider import SchwabDataProvider


CODE = "C0.Xy9-abcDEF123_ghi456"


@pytest.fixture()
def provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SchwabDataProvider:
    """A provider with credentials on disk and no network."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "credentials.yaml").write_text(
        "schwab:\n"
        '  app_key: "A" * 0\n'.replace('"A" * 0', '"abcdefghijklmnopqrstuvwxyz012345"') +
        '  app_secret: "0123456789abcdef"\n'
        '  callback_url: "https://127.0.0.1"\n'
        f'  tokens_file: "{(cfg / "schwab_tokens.json").as_posix()}"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "src.data.schwab_provider.resolve_config_dir", lambda: cfg, raising=False
    )
    return SchwabDataProvider()


class _Resp:
    ok = True
    status_code = 200
    text = "ok"

    @staticmethod
    def json() -> dict:
        return {
            "access_token": "at", "refresh_token": "rt",
            "expires_in": 1800, "token_type": "Bearer", "scope": "api",
        }


@pytest.fixture()
def captured(provider: SchwabDataProvider, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Records the code complete_auth extracted, without hitting Schwab."""
    seen: list[str] = []

    def fake_post(grant_type: str, code: str):        # noqa: ANN202
        seen.append(code)
        return _Resp()

    monkeypatch.setattr(provider, "_post_oauth_token", fake_post)
    monkeypatch.setattr(provider, "_write_tokens", lambda *a, **k: None)
    return seen


# --------------------------------------------------------------------------
# The regression: a decoded "@" used to fail outright.
# --------------------------------------------------------------------------
def test_decoded_at_sign_is_accepted(provider, captured):
    """The paste shape that used to raise. This is the bug."""
    provider.complete_auth(f"https://127.0.0.1/?code={CODE}@&session=abc123")
    assert captured == [f"{CODE}@"]


def test_encoded_at_sign_still_works(provider, captured):
    """The shape the old slice handled must keep working."""
    provider.complete_auth(f"https://127.0.0.1/?code={CODE}%40&session=abc123")
    assert captured == [f"{CODE}@"]


def test_both_forms_yield_an_identical_code(provider, captured):
    provider.complete_auth(f"https://127.0.0.1/?code={CODE}%40&session=s")
    provider.complete_auth(f"https://127.0.0.1/?code={CODE}@&session=s")
    assert captured[0] == captured[1]


# --------------------------------------------------------------------------
# Other shapes a real address bar produces.
# --------------------------------------------------------------------------
def test_session_parameter_before_the_code(provider, captured):
    """Parameter order is not guaranteed; the old index() slice assumed it."""
    provider.complete_auth(f"https://127.0.0.1/?session=abc&code={CODE}%40")
    assert captured == [f"{CODE}@"]


def test_code_without_a_trailing_at_sign(provider, captured):
    """The old slice needed a '%40' to exist at all and raised without one."""
    provider.complete_auth(f"https://127.0.0.1/?code={CODE}&session=abc")
    assert captured == [CODE]


def test_surrounding_whitespace_from_copy_paste(provider, captured):
    provider.complete_auth(f"  https://127.0.0.1/?code={CODE}%40&session=a  \n")
    assert captured == [f"{CODE}@"]


def test_percent_40_appearing_before_the_code(provider, captured):
    """Would have sliced backwards and produced nonsense, not an error."""
    provider.complete_auth(f"https://127.0.0.1/?state=a%40b&code={CODE}%40")
    assert captured == [f"{CODE}@"]


def test_http_callback_is_accepted(provider, captured):
    provider.complete_auth(f"http://127.0.0.1:8182/?code={CODE}%40")
    assert captured == [f"{CODE}@"]


def test_extra_parameters_are_ignored(provider, captured):
    provider.complete_auth(
        f"https://127.0.0.1/?session=x&code={CODE}%40&foo=bar&baz=1"
    )
    assert captured == [f"{CODE}@"]


# --------------------------------------------------------------------------
# Failure is reported clearly rather than silently producing a bad code.
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "bad",
    [
        "https://127.0.0.1/",                       # approved but no code
        "https://127.0.0.1/?session=abc",           # other params only
        "not a url at all",
        "",
        "   ",
        "https://127.0.0.1/?code=",                 # present but empty
        "https://127.0.0.1/?code=%20%20",           # whitespace only
    ],
)
def test_missing_code_raises_a_useful_error(provider, captured, bad):
    with pytest.raises(ValueError) as exc:
        provider.complete_auth(bad)
    msg = str(exc.value)
    assert "auth code" in msg
    # The message should show what to paste instead of just saying "failed".
    assert "code=" in msg
    assert captured == []   # nothing was sent to Schwab


def test_no_token_exchange_is_attempted_when_parsing_fails(provider, captured):
    with pytest.raises(ValueError):
        provider.complete_auth("https://127.0.0.1/?nope=1")
    assert captured == []
