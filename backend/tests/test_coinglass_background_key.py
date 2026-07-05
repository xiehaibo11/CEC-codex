"""resolve_background_coinglass_key: key resolution for user-less background
jobs (paper-trader cycle, rolling validation)."""
from types import SimpleNamespace

import api.coinglass.keys as keys_mod
from api.coinglass.keys import resolve_background_coinglass_key


class _FakeQuery:
    def __init__(self, records):
        self._records = records

    def limit(self, n):
        return _FakeQuery(self._records[:n])

    def all(self):
        return self._records


class _FakeDb:
    def __init__(self, records):
        self._records = records

    def query(self, model):
        return _FakeQuery(self._records)


def test_server_key_wins(monkeypatch):
    monkeypatch.setattr(keys_mod, "_server_coinglass_key", lambda: "srv-key")
    key, source = resolve_background_coinglass_key(_FakeDb([]))
    assert (key, source) == ("srv-key", "server")


def test_single_user_key_fallback(monkeypatch):
    monkeypatch.setattr(keys_mod, "_server_coinglass_key", lambda: "")
    monkeypatch.setattr(keys_mod, "decrypt_private_key", lambda blob: "user-key")
    record = SimpleNamespace(api_key_encrypted="enc", user_id=3)
    key, source = resolve_background_coinglass_key(_FakeDb([record]))
    assert (key, source) == ("user-key", "user")


def test_multiple_user_keys_refuse_to_guess(monkeypatch):
    monkeypatch.setattr(keys_mod, "_server_coinglass_key", lambda: "")
    records = [SimpleNamespace(api_key_encrypted="a", user_id=1),
               SimpleNamespace(api_key_encrypted="b", user_id=2)]
    key, source = resolve_background_coinglass_key(_FakeDb(records))
    assert (key, source) == ("", "none")


def test_no_keys_at_all(monkeypatch):
    monkeypatch.setattr(keys_mod, "_server_coinglass_key", lambda: "")
    key, source = resolve_background_coinglass_key(_FakeDb([]))
    assert (key, source) == ("", "none")
