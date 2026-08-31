"""Shared test setup.

WHY THIS EXISTS
---------------
Every API route now requires a session. Six test modules predate that and build
a TestClient directly, so from the guard's point of view they became anonymous
callers and started collecting 401s. The fix is to sign them in, not to loosen
the guard.

ORDERING MATTERS HERE
---------------------
The override is installed at SESSION scope. A function-scoped fixture is not
early enough: several of those modules build their fixtures at module scope --
posting a backtest once and reusing the id -- and those run before any
function-scoped fixture, so the setup itself was collecting the 401.

tests/test_auth.py is exempted per-test, because it is the file asserting the
guard actually refuses people. Exempting it would leave a security suite that
proves nothing.
"""

import pytest

from api import auth as auth_mod
from api.auth import require_user
from api.main import app
from db.users import User

#: A stand-in for a signed-in operator. Never written to a database -- the
#: dependency is replaced outright, so nothing looks this user up.
TEST_USER = User(id=1, username="testrunner", password_hash="", full_name="Test Runner",
                 email="test@example.invalid", country="", phone="", is_active=True)


def _override():
    return TEST_USER


#: The websocket guard is NOT a FastAPI dependency -- it reads the cookie
#: itself, because a socket handshake never runs the dependency chain. So
#: dependency_overrides does not reach it and it has to be swapped separately.
#: That asymmetry is the whole reason websockets get left unprotected, and it
#: shows up here as two overrides rather than one.
_REAL_WS_GUARD = auth_mod.user_for_websocket


async def _override_ws(websocket):
    return TEST_USER


@pytest.fixture(scope="session", autouse=True)
def _signed_in_for_the_session():
    """Installed before any module-scoped fixture gets a chance to call the API."""
    app.dependency_overrides[require_user] = _override
    auth_mod.user_for_websocket = _override_ws
    yield
    app.dependency_overrides.pop(require_user, None)
    auth_mod.user_for_websocket = _REAL_WS_GUARD


#: The suites that assert the guard REFUSES people. They must run against the
#: real dependency; exempting them would leave a security suite proving nothing.
#:
#: An explicit set, and not `name.endswith("test_auth")`, because that spelling
#: silently decided the question for every file added later: a new module called
#: test_oauth.py would have run with require_user overridden and its refusal
#: assertions would have passed without ever reaching the guard.
#:
#: test_isolation matters most of all here: it signs in as two DIFFERENT people
#: and asserts neither can reach the other's data. Under the override both
#: clients resolve to the same TEST_USER, so every assertion would pass while
#: testing nothing at all.
_SECURITY_SUITES = {"test_auth", "test_oauth_auth", "test_isolation",
                    "test_reset_auth",
                    # Asserts that a RESTORED database still refuses an
                    # anonymous caller. Without this entry that assertion runs
                    # against the override below, which can never produce a
                    # 401 -- so it would pass while testing nothing, which is
                    # the exact failure this set exists to prevent.
                    "test_backup_restore",
                    # Both assert refusals: the delete route must turn away an
                    # anonymous caller and a wrong password, and the gate suite
                    # exists precisely to watch require_user refuse an unproved
                    # address. Under the override neither reaches the guard.
                    "test_account_deletion", "test_verification_gate",
                    # Signs in as two different people and asserts
                    # neither can reach the other's saved configs.
                    "test_account_data"}


@pytest.fixture(autouse=True)
def _real_guard_for_auth_tests(request):
    """The security suites run against the genuine dependency, not the override."""
    name = getattr(request.module, "__name__", "").rsplit(".", 1)[-1]
    if name not in _SECURITY_SUITES:
        yield
        return

    app.dependency_overrides.pop(require_user, None)
    auth_mod.user_for_websocket = _REAL_WS_GUARD
    try:
        yield
    finally:
        app.dependency_overrides[require_user] = _override
        auth_mod.user_for_websocket = _override_ws
