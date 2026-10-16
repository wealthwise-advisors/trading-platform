"""Shared test setup.

WHY THIS EXISTS
---------------
Every API route runs through require_user, which resolves the workspace
account from the database (sign-in was removed on 2026-10-16). Most test
modules build a TestClient against whatever database happens to be configured,
so require_user is overridden at SESSION scope with a fixed stand-in -- the
tests do not depend on, or write an account into, a real database.

ORDERING MATTERS HERE
---------------------
The override is installed at SESSION scope. A function-scoped fixture is not
early enough: several modules build their fixtures at module scope -- posting
a backtest once and reusing the id -- and those run before any
function-scoped fixture.

A handful of modules exercise the REAL dependency against their own scratch
database -- the workspace account itself, onboarding, the cross-origin check,
a restored backup. They are listed in _REAL_WORKSPACE_SUITES below.
"""

import pytest

from api import auth as auth_mod
from api.auth import require_user
from api.main import app
from db.users import User

#: A stand-in for the workspace account. Never written to a database -- the
#: dependency is replaced outright, so nothing looks this user up.
TEST_USER = User(id=1, username="testrunner", password_hash="", full_name="Test Runner",
                 email="test@example.invalid", country="", phone="", is_active=True)


def _override():
    return TEST_USER


#: The websocket resolver is NOT a FastAPI dependency -- a socket handshake
#: never runs the dependency chain -- so dependency_overrides does not reach it
#: and it has to be swapped separately.
_REAL_WS_GUARD = auth_mod.user_for_websocket


async def _override_ws(websocket):
    return TEST_USER


@pytest.fixture(scope="session", autouse=True)
def _workspace_for_the_session():
    """Installed before any module-scoped fixture gets a chance to call the API."""
    app.dependency_overrides[require_user] = _override
    auth_mod.user_for_websocket = _override_ws
    yield
    app.dependency_overrides.pop(require_user, None)
    auth_mod.user_for_websocket = _REAL_WS_GUARD


#: Modules that run against the REAL require_user and their own scratch
#: database, because what they test IS the workspace account: which account it
#: resolves to, onboarding stored on it, the cross-origin refusal, and a
#: restored backup coming up as the same workspace. Under the override every
#: one of those would be answered by the stand-in above and prove nothing.
#:
#: An explicit set, not a name pattern, so a new file is never swept in or out
#: by accident.
_REAL_WORKSPACE_SUITES = {"test_isolation", "test_backup_restore",
                          "test_account_deletion", "test_account_data",
                          "test_live_sessions"}


@pytest.fixture(autouse=True)
def _real_workspace_for_its_suites(request):
    """Those suites run against the genuine dependency, not the override."""
    name = getattr(request.module, "__name__", "").rsplit(".", 1)[-1]
    if name not in _REAL_WORKSPACE_SUITES:
        yield
        return

    app.dependency_overrides.pop(require_user, None)
    auth_mod.user_for_websocket = _REAL_WS_GUARD
    try:
        yield
    finally:
        app.dependency_overrides[require_user] = _override
        auth_mod.user_for_websocket = _override_ws
