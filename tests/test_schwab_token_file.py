"""The Schwab token file is never left half-written.

It used to be emptied and then rewritten in place: a restart in between left an
empty file, and the app had no market data until sir sent a new token.
"""
import datetime
import json

import pytest

from src.data import schwab_provider
from src.data.schwab_provider import SchwabDataProvider

NOW = datetime.datetime(2026, 11, 13, 9, 0)


def _provider(path) -> SchwabDataProvider:
    p = object.__new__(SchwabDataProvider)
    p._tokens_file = str(path)
    return p


def test_a_token_save_replaces_the_file_whole(tmp_path):
    path = tmp_path / "schwab_tokens.json"
    _provider(path)._write_tokens(NOW, NOW, {"access_token": "new"})
    assert json.loads(path.read_text())["token_dictionary"] == {"access_token": "new"}
    assert not (tmp_path / "schwab_tokens.json.tmp").exists()


def test_a_failed_save_keeps_the_old_tokens(tmp_path, monkeypatch):
    path = tmp_path / "schwab_tokens.json"
    path.write_text('{"token_dictionary": {"access_token": "old"}}')

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(schwab_provider.json, "dump", boom)
    with pytest.raises(OSError):
        _provider(path)._write_tokens(NOW, NOW, {"access_token": "new"})
    assert json.loads(path.read_text())["token_dictionary"] == {"access_token": "old"}
