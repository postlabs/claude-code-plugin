"""Tests for toast_env — tier preflight helpers.

Covers the HEALTH_URL derivation, backend_up()'s reachability check, and
profiles_root()'s resolution order (explicit override → Toast → Mojo → None).
"""
from __future__ import annotations

import os

import urllib.error

import _common
import toast_env


class _FakeResp:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_health_url_strips_api_segment():
    expected = _common.BASE_URL.rsplit("/api/", 1)[0] + "/health"
    assert toast_env.HEALTH_URL == expected
    assert "/api/" not in toast_env.HEALTH_URL


def test_backend_up_true_on_200(monkeypatch):
    monkeypatch.setattr(toast_env.urllib.request, "urlopen",
                        lambda url, timeout=None: _FakeResp(200))
    assert toast_env.backend_up() is True


def test_backend_up_false_on_non_200(monkeypatch):
    monkeypatch.setattr(toast_env.urllib.request, "urlopen",
                        lambda url, timeout=None: _FakeResp(503))
    assert toast_env.backend_up() is False


def test_backend_up_false_when_unreachable(monkeypatch):
    def boom(url, timeout=None):
        raise urllib.error.URLError("refused")

    monkeypatch.setattr(toast_env.urllib.request, "urlopen", boom)
    assert toast_env.backend_up() is False


def test_profiles_root_honours_explicit_override(tmp_path, monkeypatch):
    monkeypatch.setenv("TOAST_PROFILES_DIR", str(tmp_path))
    assert toast_env.profiles_root() == str(tmp_path)


def test_profiles_root_prefers_toast_over_mojo(tmp_path, monkeypatch):
    monkeypatch.delenv("TOAST_PROFILES_DIR", raising=False)
    (tmp_path / "Toast" / "profiles").mkdir(parents=True)
    (tmp_path / "Mojo" / "profiles").mkdir(parents=True)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert toast_env.profiles_root() == os.path.join(str(tmp_path), "Toast", "profiles")


def test_profiles_root_falls_back_to_mojo(tmp_path, monkeypatch):
    monkeypatch.delenv("TOAST_PROFILES_DIR", raising=False)
    (tmp_path / "Mojo" / "profiles").mkdir(parents=True)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert toast_env.profiles_root() == os.path.join(str(tmp_path), "Mojo", "profiles")


def test_profiles_root_none_when_nothing_present(tmp_path, monkeypatch):
    monkeypatch.delenv("TOAST_PROFILES_DIR", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "empty"))
    assert toast_env.profiles_root() is None


def test_profiles_root_ignores_override_that_is_not_a_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("TOAST_PROFILES_DIR", str(tmp_path / "does_not_exist"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "empty"))
    assert toast_env.profiles_root() is None
