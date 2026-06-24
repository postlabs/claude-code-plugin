"""Tests for _common.call() / report() — HTTP round-trip shaping.

call() is the single HTTP seam every connected-tier script funnels through, so
its (status, body) contract is load-bearing. The status-preservation cases here
are exactly the regression bug 0.6.2 fixed (success responses were hardcoded to
200, discarding 201/204/etc).
"""
from __future__ import annotations

import io
import json
import os
import urllib.error

import pytest

import _common


class _FakeResp:
    """Minimal stand-in for the urlopen() context manager."""

    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *exc) -> bool:
        return False


def _patch_urlopen(monkeypatch, handler) -> None:
    monkeypatch.setattr(_common.urllib.request, "urlopen", handler)


def test_success_json_returns_parsed_body(monkeypatch):
    _patch_urlopen(monkeypatch, lambda req, timeout=None: _FakeResp(200, '{"ok": true}'))
    status, body = _common.call("GET", "/x")
    assert status == 200
    assert body == {"ok": True}


def test_success_non_json_returns_text(monkeypatch):
    _patch_urlopen(monkeypatch, lambda req, timeout=None: _FakeResp(200, "plain text"))
    status, body = _common.call("GET", "/x")
    assert status == 200
    assert body == "plain text"


def test_success_preserves_real_status_not_200(monkeypatch):
    # The 0.6.2 fix: a 201 Created must come back as 201, not a hardcoded 200.
    _patch_urlopen(monkeypatch, lambda req, timeout=None: _FakeResp(201, '{"id": "z"}'))
    status, body = _common.call("POST", "/doughs", {"id": "z"})
    assert status == 201
    assert body == {"id": "z"}


def test_success_204_no_content(monkeypatch):
    # Empty body on a 204 → not JSON → text path, status still preserved.
    _patch_urlopen(monkeypatch, lambda req, timeout=None: _FakeResp(204, ""))
    status, body = _common.call("DELETE", "/doughs/z")
    assert status == 204
    assert body == ""


def test_http_error_json_uses_real_code(monkeypatch):
    def raise_404(req, timeout=None):
        raise urllib.error.HTTPError(
            "http://x", 404, "Not Found", {}, io.BytesIO(b'{"detail": "nope"}'))

    _patch_urlopen(monkeypatch, raise_404)
    status, body = _common.call("GET", "/doughs/missing")
    assert status == 404
    assert body == {"detail": "nope"}


def test_http_error_non_json_returns_text(monkeypatch):
    def raise_422(req, timeout=None):
        raise urllib.error.HTTPError(
            "http://x", 422, "Unprocessable", {}, io.BytesIO(b"not json"))

    _patch_urlopen(monkeypatch, raise_422)
    status, body = _common.call("PUT", "/doughs/z", {})
    assert status == 422
    assert body == "not json"


def test_backend_unreachable_returns_status_zero(monkeypatch):
    def raise_urlerror(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    _patch_urlopen(monkeypatch, raise_urlerror)
    status, body = _common.call("GET", "/health")
    assert status == 0
    assert isinstance(body, dict) and "error" in body
    assert "backend unreachable" in body["error"]


def test_body_is_json_encoded_on_the_wire(monkeypatch):
    captured = {}

    def capture(req, timeout=None):
        captured["data"] = req.data
        captured["method"] = req.get_method()
        return _FakeResp(200, "{}")

    _patch_urlopen(monkeypatch, capture)
    _common.call("POST", "/x", {"a": 1})
    assert captured["method"] == "POST"
    assert json.loads(captured["data"]) == {"a": 1}


@pytest.mark.parametrize("status, expected_rc", [(200, 0), (201, 0), (299, 0),
                                                 (400, 1), (404, 1), (500, 1), (0, 1)])
def test_report_exit_code_follows_2xx(status, expected_rc, capsys):
    rc = _common.report(status, {"k": "v"})
    assert rc == expected_rc
    out = json.loads(capsys.readouterr().out)
    assert out == {"status": status, "body": {"k": "v"}}


# --- resolve_active_profile: registry↔disk correlation -------------------

def _seed_profiles(root, layout):
    """layout: {profile: [dough_id, ...]} → create doughs/<id-as-path> dirs."""
    for prof, ids in layout.items():
        for i in ids:
            (root / prof / "doughs" / os.path.join(*i.split("."))).mkdir(
                parents=True, exist_ok=True)
        (root / prof / "doughs").mkdir(parents=True, exist_ok=True)


def test_resolve_active_profile_picks_best_covered(tmp_path):
    # 'active' carries every live id (incl. the user dough); 'local' lacks it;
    # 'empty' has a doughs dir but nothing in it.
    (tmp_path / "empty" / "doughs").mkdir(parents=True)
    _seed_profiles(tmp_path, {
        "active": ["basic.greet", "advanced.x.y", "user.mine"],
        "local": ["basic.greet", "advanced.x.y"],
    })
    live = ["basic.greet", "advanced.x.y", "user.mine"]
    active, ev = _common.resolve_active_profile(
        str(tmp_path), ["active", "empty", "local"], live)
    assert active == "active"
    assert ev["coverage"] == {"active": 3, "empty": 0, "local": 2}
    assert ev["match_ratio"] == 1.0


def test_resolve_active_profile_tie_is_undetermined(tmp_path):
    _seed_profiles(tmp_path, {
        "a": ["basic.greet", "advanced.x.y"],
        "b": ["basic.greet", "advanced.x.y"],
    })
    live = ["basic.greet", "advanced.x.y"]
    active, ev = _common.resolve_active_profile(str(tmp_path), ["a", "b"], live)
    assert active is None
    assert ev["reason"] == "ambiguous_tie"
    assert sorted(ev["candidates"]) == ["a", "b"]


def test_resolve_active_profile_no_match_is_undetermined(tmp_path):
    (tmp_path / "a" / "doughs").mkdir(parents=True)
    active, ev = _common.resolve_active_profile(str(tmp_path), ["a"], ["user.mine"])
    assert active is None
    assert ev["reason"] == "no_disk_match"


def test_resolve_active_profile_backend_down(tmp_path, monkeypatch):
    # ids=None path: call() reports backend unreachable → undetermined, no crash.
    monkeypatch.setattr(_common, "call", lambda *a, **k: (0, {"error": "x"}))
    active, ev = _common.resolve_active_profile(str(tmp_path), [])
    assert active is None
    assert ev["reason"] == "backend_unreachable"


def test_live_dough_ids_parses_envelope(monkeypatch):
    monkeypatch.setattr(_common, "call", lambda *a, **k: (
        200, {"doughs": [{"id": "user.a"}, {"id": "basic.b"}, {"no": "id"}]}))
    assert _common.live_dough_ids() == ["user.a", "basic.b"]
