"""Chart templates and server-side settings (upgrade plan, Phase 1, Feature 10).

Chart style, VWAP levels, Volume Avg, Volume Profile defaults, colours, the time zone, the
watchlist and price alerts lived in each browser's storage, so they differed between the
owner's laptop and sir's. Stored on the server against the workspace account they are the
same everywhere; named chart templates are saved the same way as backtest configurations.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from db import connection
from db import users as repo


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(connection, "DB_PATH", tmp_path / "settings.db")
    return tmp_path


@pytest.fixture
def client(db):
    with TestClient(app) as c:
        yield c


def make_user(username="trader", email="t@example.com") -> int:
    return repo.create_user(username, "!", full_name="A Trader", email=email, country="IN", has_password=False)


# ── settings: one document per account, versioned ───────────────────────────

def test_settings_start_empty_and_round_trip(client, db):
    first = client.get("/api/account/settings").json()
    assert first == {"settings": {}, "version": 0, "updated_at": None}

    r = client.put("/api/account/settings", json={"settings": {"chartStyle": '{"type":"candles"}'}, "version": 0})
    assert r.status_code == 200, r.text
    assert r.json()["version"] == 1

    again = client.get("/api/account/settings").json()
    assert again["settings"] == {"chartStyle": '{"type":"candles"}'}
    assert again["version"] == 1


def test_a_stale_version_is_refused_not_overwritten(client, db):
    """Two tabs: the second save, made against the old version, must not silently win."""
    client.put("/api/account/settings", json={"settings": {"zone": "-60"}, "version": 0})
    stale = client.put("/api/account/settings", json={"settings": {"zone": "0"}, "version": 0})
    assert stale.status_code == 409
    assert client.get("/api/account/settings").json()["settings"] == {"zone": "-60"}


def test_an_unknown_setting_is_refused(client, db):
    r = client.put("/api/account/settings", json={"settings": {"sneaky": 1}, "version": 0})
    assert r.status_code == 400
    assert "sneaky" in r.json()["detail"]


def test_an_oversized_settings_document_is_refused(client, db):
    r = client.put("/api/account/settings", json={"settings": {"watchlist": "X" * 600_000}, "version": 0})
    assert r.status_code == 400


def test_a_setting_that_is_not_text_is_refused(client, db):
    """Values travel as the exact strings browser storage holds; anything else would be
    written into storage and read back as junk by the app's own loaders."""
    r = client.put("/api/account/settings", json={"settings": {"zone": {"a": 1}}, "version": 0})
    assert r.status_code == 400
    assert "zone" in r.json()["detail"]


def test_a_template_with_the_wrong_kind_of_value_is_refused(client, db):
    bad = [{"chartStyle": {"type": "bars"}}, {"studies": "bb"}, {"studies": {"bb": "yes"}}]
    for t in bad:
        assert client.put("/api/account/templates/Bad", json={"template": t}).status_code == 400, t
    assert client.get("/api/account/templates").json() == []


def test_another_website_cannot_write_settings(client, db):
    r = client.put("/api/account/settings", json={"settings": {"zone": 0}, "version": 0},
                   headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


# ── templates: named chart setups, one of them the default ───────────────────

def test_save_list_replace_and_delete_a_template(client, db):
    assert client.get("/api/account/templates").json() == []
    r = client.put("/api/account/templates/Scalping", json={"template": {"studies": {"vwap": True}}})
    assert r.status_code == 200, r.text
    assert r.json() == {"name": "Scalping", "saved_at": r.json()["saved_at"], "is_default": False,
                        "template": {"studies": {"vwap": True}}}

    client.put("/api/account/templates/Scalping", json={"template": {"studies": {"vwap": False}}})
    listed = client.get("/api/account/templates").json()
    assert len(listed) == 1 and listed[0]["template"] == {"studies": {"vwap": False}}

    assert client.delete("/api/account/templates/Scalping").status_code == 200
    assert client.get("/api/account/templates").json() == []


def test_only_one_template_is_the_default(client, db):
    client.put("/api/account/templates/A", json={"template": {}})
    client.put("/api/account/templates/B", json={"template": {}})
    assert client.post("/api/account/templates/A/default").status_code == 200
    assert client.post("/api/account/templates/B/default").status_code == 200
    by = {t["name"]: t["is_default"] for t in client.get("/api/account/templates").json()}
    assert by == {"A": False, "B": True}
    # Saving over the default keeps it the default.
    client.put("/api/account/templates/B", json={"template": {"studies": {}}})
    assert {t["name"]: t["is_default"] for t in client.get("/api/account/templates").json()}["B"] is True


def test_clearing_the_default(client, db):
    client.put("/api/account/templates/A", json={"template": {}})
    client.post("/api/account/templates/A/default")
    assert client.delete("/api/account/templates/default").status_code == 200
    assert client.get("/api/account/templates").json()[0]["is_default"] is False


def test_template_names_and_sizes_are_checked(client, db):
    assert client.put("/api/account/templates/%20", json={"template": {}}).status_code == 400
    assert client.put("/api/account/templates/" + "x" * 81, json={"template": {}}).status_code == 400
    assert client.put("/api/account/templates/Big", json={"template": {"chartStyle": "x" * 70_000}}).status_code == 400
    assert client.put("/api/account/templates/Odd", json={"template": {"sneaky": 1}}).status_code == 400


def test_unknown_templates_are_404(client, db):
    assert client.delete("/api/account/templates/Nope").status_code == 404
    assert client.post("/api/account/templates/Nope/default").status_code == 404


# ── the data layer: one account never sees another's ─────────────────────────

def test_one_accounts_settings_and_templates_are_invisible_to_another(db):
    a, b = make_user("a", "a@example.com"), make_user("b", "b@example.com")
    repo.put_settings(a, '{"zone": -60}', 0)
    repo.save_template(a, "Mine", "{}")
    assert repo.get_settings(b) is None
    assert repo.list_templates(b) == []
    assert repo.delete_template(b, "Mine") is False
    assert len(repo.list_templates(a)) == 1


def test_closing_the_account_takes_settings_and_templates_with_it(db):
    a = make_user()
    repo.put_settings(a, '{"zone": -60}', 0)
    repo.save_template(a, "Mine", "{}")
    repo.delete_account(a)
    assert repo.get_settings(a) is None
    assert repo.list_templates(a) == []
