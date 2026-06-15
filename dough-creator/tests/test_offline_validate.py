"""Tests for offline_validate helpers — discovery, shim store, provenance merge.

Importing this module loads the vendored engine slice (pydantic), which is the
intended standalone-validation dependency. The behaviours pinned here are the
ones with real consequences: dir discovery pruning, the workspace-scoped shim
that downgrades unknown refs to warnings, and — most importantly — that a
static-validation pass never overwrites an engine-verified provenance record.
"""
from __future__ import annotations

import offline_validate as ov


# ── ShimStore ─────────────────────────────────────────────────────────────

def test_shim_known_id_not_recorded_as_external():
    shim = ov.ShimStore({"user.known"})
    assert shim.dough_exists("user.known") is True
    assert shim.external_refs == []


def test_shim_unknown_id_recorded_once():
    shim = ov.ShimStore({"user.known"})
    assert shim.dough_exists("user.other") is True
    assert shim.dough_exists("user.other") is True  # idempotent
    assert shim.external_refs == ["user.other"]


def test_shim_get_dough_is_none():
    assert ov.ShimStore(set()).get_dough("anything") is None


# ── find_dough_dirs ───────────────────────────────────────────────────────

def _write(path, text="id: x\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_find_dough_dirs_prunes_infra_and_dotdirs(tmp_path):
    _write(tmp_path / "a" / "dough.yaml", "id: user.a\n")
    _write(tmp_path / "b" / "c" / "dough.yaml", "id: user.bc\n")
    _write(tmp_path / "vendor" / "x" / "dough.yaml")
    _write(tmp_path / "node_modules" / "d" / "dough.yaml")
    _write(tmp_path / ".hidden" / "dough.yaml")

    found = {p.name for p in ov.find_dough_dirs(tmp_path)}
    assert found == {"a", "c"}


def test_collect_known_ids_reads_id_fields(tmp_path):
    _write(tmp_path / "a" / "dough.yaml", "id: user.a\n")
    _write(tmp_path / "b" / "dough.yaml", "id: user.b\n")
    dirs = ov.find_dough_dirs(tmp_path)
    assert ov.collect_known_ids(dirs) == {"user.a", "user.b"}


# ── resolve_workspace ─────────────────────────────────────────────────────

def test_resolve_workspace_returns_target_when_not_a_dough_dir(tmp_path):
    assert ov.resolve_workspace(tmp_path, is_dough_dir=False) == tmp_path


def test_resolve_workspace_finds_provenance_in_parent(tmp_path):
    ws = tmp_path / "ws"
    dough = ws / "mydough"
    dough.mkdir(parents=True)
    (ws / "provenance.yaml").write_text("artifacts: {}\n", encoding="utf-8")
    assert ov.resolve_workspace(dough, is_dough_dir=True) == ws


def test_resolve_workspace_finds_provenance_two_levels_up(tmp_path):
    ws = tmp_path / "ws"
    dough = ws / "sub" / "mydough"
    dough.mkdir(parents=True)
    (ws / "provenance.yaml").write_text("artifacts: {}\n", encoding="utf-8")
    assert ov.resolve_workspace(dough, is_dough_dir=True) == ws


def test_resolve_workspace_defaults_to_parent(tmp_path):
    dough = tmp_path / "loose" / "mydough"
    dough.mkdir(parents=True)
    assert ov.resolve_workspace(dough, is_dough_dir=True) == dough.parent


# ── update_provenance ─────────────────────────────────────────────────────

def test_update_provenance_none_when_nothing_passed(tmp_path):
    assert ov.update_provenance(tmp_path, []) is None


def test_update_provenance_writes_static_record(tmp_path):
    path = ov.update_provenance(tmp_path, [{"id": "user.a"}])
    assert path is not None
    doc = ov.load_yaml(tmp_path / "provenance.yaml")
    rec = doc["artifacts"]["user.a"]
    assert rec["validated"] == "static"
    assert rec["engine_core"] == ov.ENGINE_REV
    assert rec["at"]


def test_update_provenance_does_not_clobber_engine_verified(tmp_path):
    (tmp_path / "provenance.yaml").write_text(
        "artifacts:\n"
        "  user.a:\n"
        "    validated: engine\n"
        "    engine_core: oldrev\n"
        "    at: '2020-01-01'\n",
        encoding="utf-8",
    )
    ov.update_provenance(tmp_path, [{"id": "user.a"}])
    rec = ov.load_yaml(tmp_path / "provenance.yaml")["artifacts"]["user.a"]
    assert rec["validated"] == "engine"      # engine-verified outranks static
    assert rec["engine_core"] == "oldrev"    # untouched


def test_update_provenance_replaces_prior_static(tmp_path):
    (tmp_path / "provenance.yaml").write_text(
        "artifacts:\n"
        "  user.a:\n"
        "    validated: static\n"
        "    engine_core: oldrev\n"
        "    at: '2020-01-01'\n",
        encoding="utf-8",
    )
    ov.update_provenance(tmp_path, [{"id": "user.a"}])
    rec = ov.load_yaml(tmp_path / "provenance.yaml")["artifacts"]["user.a"]
    assert rec["engine_core"] == ov.ENGINE_REV  # a fresh static pass refreshes it
