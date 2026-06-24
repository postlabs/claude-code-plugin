"""Tests for tool_runner — input parsing, result shaping, symbol resolution.

_resolve is the meatiest logic: bare symbol → tools.py default, explicit
<file>.py:<symbol> form, flour-scan fallback, and the tools.py-misses →
rescan-elsewhere recovery. Each case builds a throwaway namespace-package kit on
sys.path and cleans it (and sys.modules) up after, so resolution is exercised
for real without leaking import state between tests.
"""
from __future__ import annotations

import contextlib
import sys
from pathlib import Path

import pytest

import tool_runner


# ── _parse_inputs ─────────────────────────────────────────────────────────

def test_parse_inputs_empty_is_dict():
    assert tool_runner._parse_inputs(None) == {}
    assert tool_runner._parse_inputs("") == {}


def test_parse_inputs_inline_object():
    assert tool_runner._parse_inputs('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}


def test_parse_inputs_from_file(tmp_path):
    f = tmp_path / "in.json"
    f.write_text('{"k": "v"}', encoding="utf-8")
    assert tool_runner._parse_inputs("@" + str(f)) == {"k": "v"}


def test_parse_inputs_rejects_non_object():
    with pytest.raises(ValueError):
        tool_runner._parse_inputs("[1, 2, 3]")


def test_parse_inputs_missing_file_raises_oserror(tmp_path):
    with pytest.raises(OSError):
        tool_runner._parse_inputs("@" + str(tmp_path / "nope.json"))


# ── _jsonable ─────────────────────────────────────────────────────────────

def test_jsonable_uses_model_dump():
    class Model:
        def model_dump(self, mode=None):
            return {"dumped": mode}

    assert tool_runner._jsonable(Model()) == {"dumped": "json"}


def test_jsonable_sorts_sets():
    assert tool_runner._jsonable({"b", "a", "c"}) == ["a", "b", "c"]


def test_jsonable_falls_back_to_str():
    assert tool_runner._jsonable(Path("x") / "y") == str(Path("x") / "y")


# ── _scan_flour_entries ───────────────────────────────────────────────────

def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_scan_finds_matching_entry(tmp_path):
    _write(tmp_path / "flour" / "dough.yaml",
           "id: x\nentry: levels.py:find_levels\n")
    assert tool_runner._scan_flour_entries(tmp_path, "find_levels") == "levels.py"


def test_scan_returns_none_for_unknown_symbol(tmp_path):
    _write(tmp_path / "flour" / "dough.yaml", "entry: levels.py:find_levels\n")
    assert tool_runner._scan_flour_entries(tmp_path, "missing") is None


# ── _resolve ──────────────────────────────────────────────────────────────

@contextlib.contextmanager
def _kit_on_path(parent: Path, kit_name: str):
    sys.path.insert(0, str(parent))
    try:
        yield
    finally:
        with contextlib.suppress(ValueError):
            sys.path.remove(str(parent))
        for mod in [m for m in sys.modules if m == kit_name or m.startswith(kit_name + ".")]:
            del sys.modules[mod]


def test_resolve_bare_symbol_defaults_to_tools_py(tmp_path):
    _write(tmp_path / "kitA" / "tools.py", "def greet(name):\n    return 'hi ' + name\n")
    with _kit_on_path(tmp_path, "kitA"):
        fn, ref = tool_runner._resolve(tmp_path / "kitA", "greet")
        assert ref == "tools.py:greet"
        assert fn(name="x") == "hi x"


def test_resolve_explicit_entry_form(tmp_path):
    _write(tmp_path / "kitC" / "calc.py", "def add(a, b):\n    return a + b\n")
    with _kit_on_path(tmp_path, "kitC"):
        fn, ref = tool_runner._resolve(tmp_path / "kitC", "calc.py:add")
        assert ref == "calc.py:add"
        assert fn(a=1, b=2) == 3


def test_resolve_explicit_form_requires_py_suffix(tmp_path):
    with pytest.raises(ValueError):
        tool_runner._resolve(tmp_path / "kitC", "calc:add")


def test_resolve_scans_flour_when_no_tools_py(tmp_path):
    _write(tmp_path / "kitB" / "levels.py", "def find_levels():\n    return [1, 2]\n")
    _write(tmp_path / "kitB" / "flour" / "dough.yaml", "entry: levels.py:find_levels\n")
    with _kit_on_path(tmp_path, "kitB"):
        fn, ref = tool_runner._resolve(tmp_path / "kitB", "find_levels")
        assert ref == "levels.py:find_levels"
        assert fn() == [1, 2]


def test_resolve_rescans_when_symbol_not_in_tools_py(tmp_path):
    # tools.py exists but lacks the symbol; the flour scan recovers it elsewhere.
    _write(tmp_path / "kitD" / "tools.py", "def other():\n    return 'o'\n")
    _write(tmp_path / "kitD" / "levels.py", "def special():\n    return 's'\n")
    _write(tmp_path / "kitD" / "flour" / "dough.yaml", "entry: levels.py:special\n")
    with _kit_on_path(tmp_path, "kitD"):
        fn, ref = tool_runner._resolve(tmp_path / "kitD", "special")
        assert ref == "levels.py:special"
        assert fn() == "s"


def test_resolve_raises_when_unresolvable(tmp_path):
    (tmp_path / "kitE").mkdir()
    with _kit_on_path(tmp_path, "kitE"):
        with pytest.raises(ImportError):
            tool_runner._resolve(tmp_path / "kitE", "ghost")
