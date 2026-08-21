"""Tests for kit_lifecycle.kit_bound() — the install-verify predicate.

kit_bound decides whether an installed kit actually bound its tools (the
active-profile/sys.path failure mode). It must tolerate both the list and the
{"kits": [...]} response shapes and only count a kit that exposes tools/provides.
"""
from __future__ import annotations

import os

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


# --- _tool_schema_present: the half-load (empty schema) guard ------------

def test_schema_present_true_with_inputs():
    kit = {"id": "k", "tools": [{"name": "t", "inputs": [{"name": "a"}], "outputs": []}]}
    assert kit_lifecycle._tool_schema_present(kit) is True


def test_schema_present_false_when_all_empty():
    # The exact half-load signal: tool registered, schema is [].
    kit = {"id": "k", "tools": [{"name": "t", "inputs": [], "outputs": []}]}
    assert kit_lifecycle._tool_schema_present(kit) is False


def test_schema_present_false_for_string_tools():
    assert kit_lifecycle._tool_schema_present({"id": "k", "tools": ["t"]}) is False


# --- verify_install: composition of the three checks ---------------------

def _wire(monkeypatch, kit, *, flour_status=200, active="p", persisted=("p",)):
    """Stub the network + disk seams verify_install() depends on."""
    def fake_call(method, path, body=None):
        if path == "/kits":
            return (200, {"kits": [kit]} if kit else {"kits": []})
        if path.startswith("/doughs/"):
            return (flour_status, {})
        return (200, {})
    monkeypatch.setattr(kit_lifecycle, "call", fake_call)
    monkeypatch.setattr(kit_lifecycle, "resolve_active_profile",
                        lambda *a, **k: (active, {"method": "stub"}))
    monkeypatch.setattr(kit_lifecycle, "profiles_root", lambda: "/root")
    monkeypatch.setattr(kit_lifecycle, "list_profiles", lambda root: ["p", "other"])
    monkeypatch.setattr(kit_lifecycle.os.path, "isdir",
                        lambda path: any(path.endswith(os.path.join(pr, "doughs", "mykit"))
                                         for pr in persisted))


def test_verify_install_all_green(monkeypatch):
    kit = {"id": "mykit", "tools": [{"name": "t", "inputs": [{"name": "a"}]}]}
    _wire(monkeypatch, kit, flour_status=200, active="p", persisted=("p",))
    ok, checks = kit_lifecycle.verify_install("mykit")
    assert ok is True
    assert checks["flours_registered"] and checks["persisted_on_active"]


def test_verify_install_fails_on_empty_schema(monkeypatch):
    kit = {"id": "mykit", "tools": [{"name": "t", "inputs": [], "outputs": []}]}
    _wire(monkeypatch, kit, flour_status=200, active="p", persisted=("p",))
    ok, checks = kit_lifecycle.verify_install("mykit")
    assert ok is False
    assert checks["tool_schema_present"] is False


def test_verify_install_fails_on_missing_flour(monkeypatch):
    kit = {"id": "mykit", "tools": [{"name": "t", "inputs": [{"name": "a"}]}]}
    _wire(monkeypatch, kit, flour_status=404, active="p", persisted=("p",))
    ok, checks = kit_lifecycle.verify_install("mykit")
    assert ok is False
    assert checks["flours_missing"] == ["mykit.t"]


def test_verify_install_fails_when_not_on_active_profile(monkeypatch):
    kit = {"id": "mykit", "tools": [{"name": "t", "inputs": [{"name": "a"}]}]}
    _wire(monkeypatch, kit, flour_status=200, active="p", persisted=("other",))
    ok, checks = kit_lifecycle.verify_install("mykit")
    assert ok is False
    assert checks["persisted_on_active"] is False
    assert checks["persisted_profiles"] == ["other"]


# --- the box gate over kit flours (applied BEFORE anything is copied) ------


def _make_kit(tmp_path, flours):
    """A kit dir with one dir per flour: {name: (dough_yaml, box_yaml|None)}."""
    kit = tmp_path / "mykit"
    kit.mkdir()
    (kit / "kit.yaml").write_text("id: mykit\n", encoding="utf-8")
    (kit / "tools.py").write_text("def t():\n    return {}\n", encoding="utf-8")
    for name, (dough, box) in flours.items():
        d = kit / name
        d.mkdir()
        (d / "dough.yaml").write_text(dough, encoding="utf-8")
        if box is not None:
            (d / "box.yaml").write_text(box, encoding="utf-8")
    return kit


_FLOUR = "id: mykit.t\naction:\n  tool: mykit.t\ninputs:\n  q:\n    type: string\n"
_FULL_BOX = (
    "en:\n  name: Search\n  about: searches\n"
    "  inputs:\n    q:\n      name: Query\n      description: what to search for\n"
    "ko:\n  name: 검색\n  about: 검색한다\n"
    "  inputs:\n    q:\n      name: 검색어\n      description: 무엇을 검색할지\n"
)


def test_kit_box_gate_passes_a_complete_kit(tmp_path):
    kit = _make_kit(tmp_path, {"t": (_FLOUR, _FULL_BOX)})
    issues, skipped = kit_lifecycle.kit_box_issues(str(kit))
    assert skipped is None
    assert issues == []


def test_kit_box_gate_flags_the_offending_flour_by_name(tmp_path):
    kit = _make_kit(tmp_path, {"good": (_FLOUR, _FULL_BOX), "bad": (_FLOUR, None)})
    issues, _ = kit_lifecycle.kit_box_issues(str(kit))
    assert [(i["flour"], i["code"]) for i in issues] == [("bad", "box_missing")]


def test_kit_box_gate_requires_ko_in_kit_flours(tmp_path):
    en_only = ("en:\n  name: Search\n  about: searches\n"
               "  inputs:\n    q:\n      name: Query\n      description: what\n")
    kit = _make_kit(tmp_path, {"t": (_FLOUR, en_only)})
    issues, _ = kit_lifecycle.kit_box_issues(str(kit))
    assert [i["code"] for i in issues] == ["box_locale_missing"]
    assert "`ko:`" in issues[0]["message"]


def test_kit_box_gate_ignores_non_flour_dirs(tmp_path):
    kit = _make_kit(tmp_path, {"t": (_FLOUR, _FULL_BOX)})
    (kit / "__pycache__").mkdir()
    (kit / "__pycache__" / "dough.yaml").write_text("id: junk\n", encoding="utf-8")
    issues, _ = kit_lifecycle.kit_box_issues(str(kit))
    assert issues == []
