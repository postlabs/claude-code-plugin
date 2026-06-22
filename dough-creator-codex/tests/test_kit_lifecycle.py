"""Tests for kit_lifecycle.kit_bound() — the install-verify predicate.

kit_bound decides whether an installed kit actually bound its tools (the
active-profile/sys.path failure mode). It must tolerate both the list and the
{"kits": [...]} response shapes and only count a kit that exposes tools/provides.
"""
from __future__ import annotations

import kit_lifecycle


def _fake_call(response):
    return lambda method, path, body=None: response


def test_bound_when_kit_present_with_tools(monkeypatch):
    monkeypatch.setattr(kit_lifecycle, "call",
                        _fake_call((200, [{"id": "mykit", "tools": ["t1"]}])))
    assert kit_lifecycle.kit_bound("mykit") is True


def test_bound_accepts_kits_envelope_and_provides(monkeypatch):
    monkeypatch.setattr(kit_lifecycle, "call",
                        _fake_call((200, {"kits": [{"id": "mykit", "provides": ["p"]}]})))
    assert kit_lifecycle.kit_bound("mykit") is True


def test_not_bound_when_kit_has_no_tools(monkeypatch):
    monkeypatch.setattr(kit_lifecycle, "call",
                        _fake_call((200, [{"id": "mykit"}])))
    assert kit_lifecycle.kit_bound("mykit") is False


def test_not_bound_when_id_mismatch(monkeypatch):
    monkeypatch.setattr(kit_lifecycle, "call",
                        _fake_call((200, [{"id": "other", "tools": ["t"]}])))
    assert kit_lifecycle.kit_bound("mykit") is False


def test_not_bound_on_non_200(monkeypatch):
    monkeypatch.setattr(kit_lifecycle, "call",
                        _fake_call((500, {"error": "boom"})))
    assert kit_lifecycle.kit_bound("mykit") is False


def test_not_bound_on_unexpected_body_type(monkeypatch):
    monkeypatch.setattr(kit_lifecycle, "call",
                        _fake_call((200, "a plain string")))
    assert kit_lifecycle.kit_bound("mykit") is False
