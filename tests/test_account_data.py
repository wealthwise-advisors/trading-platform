"""Saved configurations and onboarding, for the workspace the app runs as.

Sign-in was removed on 2026-10-16: every request is the workspace account
(db.users.workspace_user), so these tests drive the app the way a visitor
does -- open it, no login.

What went with sign-in: data export (its /api/auth/export route), the
anonymous-caller refusals, sign-out, and the login throttle. What stays is
everything the app still does, plus the data-layer guarantee that two
accounts' configurations never mix -- tested at the repository, since over
HTTP there is only one account now.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from db import connection
from db import users as repo


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "account.db")
    return tmp_path


@pytest.fixture
def client(db):
    with TestClient(app) as c:
        yield c


def make_user(username="trader", email="t@example.com") -> int:
    """An account row. No password: nothing signs in any more."""
    return repo.create_user(username, "!", full_name="A Trader", email=email,
                            country="IN", has_password=False)


# ── saved configurations: the round trip ─────────────────────────────────────

def test_save_list_update_and_delete(client, db):
    assert client.get("/api/account/configs").json() == []

    r = client.put("/api/account/configs/My%20Setup",
                   json={"config": {"symbol": "ES", "timeframe": "5m"}})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "My Setup"

    listed = client.get("/api/account/configs").json()
    assert len(listed) == 1
    assert listed[0]["config"] == {"symbol": "ES", "timeframe": "5m"}

    # Saving the same name replaces rather than duplicating.
    client.put("/api/account/configs/My%20Setup",
               json={"config": {"symbol": "NQ", "timeframe": "1m"}})
    listed = client.get("/api/account/configs").json()
    assert len(listed) == 1
    assert listed[0]["config"]["symbol"] == "NQ"

    assert client.delete("/api/account/configs/My%20Setup").status_code == 200
    assert client.get("/api/account/configs").json() == []


def test_a_second_device_sees_the_same_configs(client, db):
    """A different client with its own cookie jar: the second-device case.

    The reason configurations moved off the browser: they are server-side, so
    any browser that opens the link sees them.
    """
    client.put("/api/account/configs/Shared", json={"config": {"symbol": "ES"}})
    with TestClient(app) as other_device:
        assert [c["name"] for c in other_device.get("/api/account/configs").json()] == ["Shared"]


def test_deleting_an_unknown_name_is_404(client, db):
    assert client.delete("/api/account/configs/never-existed").status_code == 404


def test_an_oversized_payload_is_refused(client, db):
    r = client.put("/api/account/configs/Huge",
                   json={"config": {"blob": "x" * 70_000}})
    assert r.status_code == 400
    assert "too large" in r.json()["detail"].lower()


def test_another_website_cannot_write_or_delete_configs(client, db):
    """The protection that remains without sign-in: the cross-origin check.

    With no session, the only thing stopping a page on another site from
    rewriting this workspace's configurations through a visitor's browser is
    that the request does not come from here.
    """
    client.put("/api/account/configs/Mine", json={"config": {"symbol": "ES"}})
    evil = {"Origin": "https://evil.example"}
    assert client.put("/api/account/configs/Mine", json={"config": {"symbol": "XX"}},
                      headers=evil).status_code == 403
    assert client.delete("/api/account/configs/Mine", headers=evil).status_code == 403
    assert client.get("/api/account/configs").json()[0]["config"]["symbol"] == "ES"


# ── saved configurations: isolation, at the data layer ───────────────────────

def test_one_accounts_configs_are_invisible_to_another(db):
    alice, bob = make_user("alice", "a@example.com"), make_user("bob", "b@example.com")
    repo.save_config(alice, "Alices", '{"symbol": "ES"}')
    assert repo.list_configs(bob) == []


def test_one_account_cannot_delete_anothers_config(db):
    alice, bob = make_user("alice", "a@example.com"), make_user("bob", "b@example.com")
    repo.save_config(alice, "Secret", '{"symbol": "ES"}')
    assert repo.delete_config(bob, "Secret") is False
    assert [c["name"] for c in repo.list_configs(alice)] == ["Secret"]


def test_the_same_name_is_two_different_configs(db):
    """The primary key is (user_id, name), so a common name is not a collision."""
    alice, bob = make_user("alice", "a@example.com"), make_user("bob", "b@example.com")
    repo.save_config(alice, "Default", '{"symbol": "ES"}')
    repo.save_config(bob, "Default", '{"symbol": "NQ"}')
    assert repo.list_configs(alice)[0]["payload"] == '{"symbol": "ES"}'
    assert repo.list_configs(bob)[0]["payload"] == '{"symbol": "NQ"}'


def test_closing_the_account_takes_the_configs_with_it(client, db):
    """scripts/manage_users.py delete must not leave a closed account's data behind."""
    client.put("/api/account/configs/Doomed", json={"config": {"symbol": "ES"}})
    repo.delete_account(repo.workspace_user().id)

    conn = connection.connect()
    try:
        left = conn.execute("SELECT COUNT(*) AS n FROM user_configs").fetchone()["n"]
    finally:
        conn.close()
    assert left == 0


# ── onboarding ───────────────────────────────────────────────────────────────

def test_a_new_workspace_is_not_onboarded(client, db):
    assert client.get("/api/auth/me").json()["onboarded"] is False


def test_finishing_onboarding_sticks(client, db):
    assert client.post("/api/auth/onboarded").status_code == 200
    assert client.get("/api/auth/me").json()["onboarded"] is True
    # And from another browser, which localStorage could never do.
    with TestClient(app) as other:
        assert other.get("/api/auth/me").json()["onboarded"] is True


def test_finishing_twice_does_not_move_the_date(client, db):
    client.post("/api/auth/onboarded")
    uid = repo.workspace_user().id

    def onboarded_at():
        conn = connection.connect()
        try:
            return conn.execute("SELECT onboarded_at FROM users WHERE id = ?",
                                (uid,)).fetchone()["onboarded_at"]
        finally:
            conn.close()

    first = onboarded_at()
    client.post("/api/auth/onboarded")
    assert onboarded_at() == first
