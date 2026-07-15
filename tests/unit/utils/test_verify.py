"""Tests for utils.verify."""

from types import SimpleNamespace

import requests
import pytest

from utils import verify as verify_module


def test_verify_retries_then_succeeds(monkeypatch, capsys):
    "verify retries connection errors and prints response json on success."

    calls = {"count": 0}

    def fake_get(url, timeout):  # pylint: disable=unused-argument
        calls["count"] += 1
        if calls["count"] < 3:
            raise requests.exceptions.ConnectionError("not yet")
        return SimpleNamespace(status_code=200, json=lambda: {"ok": True})

    monkeypatch.setattr(verify_module.requests, "get", fake_get)
    monkeypatch.setattr(verify_module.time, "sleep", lambda _: None)

    verify_module.verify(5001)
    out = capsys.readouterr().out
    assert "Lute is running:" in out
    assert '"ok": true' in out


def test_verify_raises_after_timeout(monkeypatch):
    "verify raises a clear timeout error after repeated connection failures."

    def always_fail(url, timeout):  # pylint: disable=unused-argument
        raise requests.exceptions.ConnectionError("still down")

    monkeypatch.setattr(verify_module.requests, "get", always_fail)
    monkeypatch.setattr(verify_module.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="did not respond within 60 seconds"):
        verify_module.verify(5001)
