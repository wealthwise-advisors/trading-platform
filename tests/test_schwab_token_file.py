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


# ── Saves that overlap (2026-11-16 backend log: "[WinError 32] ... schwab_tokens.json.tmp
# -> schwab_tokens.json", WinError 5 and WinError 2, many times in a row). Both writers
# shared one .tmp name and gave up on the first "file in use", printing and dropping
# the freshly refreshed token. ──
import threading  # noqa: E402

from src.data.schwabdev.api import Client  # noqa: E402


def _client(path) -> Client:
    c = object.__new__(Client)
    c._tokens_file = str(path)
    return c


def test_overlapping_saves_from_both_writers_all_land(tmp_path, capsys):
    path = tmp_path / "schwab_tokens.json"
    errors = []

    def save(i):
        try:
            if i % 2:
                _provider(path)._write_tokens(NOW, NOW, {"access_token": f"t{i}"})
            else:
                _client(path)._write_tokens_file(NOW, NOW, {"access_token": f"t{i}"})
        except Exception as e:  # pragma: no cover - the failure being tested for
            errors.append(e)

    threads = [threading.Thread(target=save, args=(i,)) for i in range(24)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert "WinError" not in capsys.readouterr().out          # schwabdev printed and dropped these
    assert json.loads(path.read_text())["token_dictionary"]["access_token"].startswith("t")
    assert list(tmp_path.glob("*.tmp")) == []


@pytest.mark.parametrize("writer", ["provider", "client"])
def test_a_save_waits_out_a_reader_holding_the_file(tmp_path, writer):
    """On Windows the file cannot be replaced while another thread has it open."""
    path = tmp_path / "schwab_tokens.json"
    path.write_text(json.dumps({"token_dictionary": {"access_token": "old"}}))
    reader = open(path)                                       # e.g. _read_tokens mid-read
    save = (lambda: _provider(path)._write_tokens(NOW, NOW, {"access_token": "new"})) if writer == "provider" \
        else (lambda: _client(path)._write_tokens_file(NOW, NOW, {"access_token": "new"}))
    t = threading.Thread(target=save)
    t.start()
    threading.Event().wait(0.3)
    reader.close()
    t.join(timeout=10)
    assert json.loads(path.read_text())["token_dictionary"] == {"access_token": "new"}
    assert list(tmp_path.glob("*.tmp")) == []
