"""Tests for dough_publish.publish() — payload shaping + existence-probe branch.

publish() reads dough.yaml/box.yaml, strips server-managed keys, derives the id,
lifts en.name/en.about to top-level extras, and chooses POST (new) vs PUT
(existing) from a GET probe — refusing to act when the probe is inconclusive
(5xx). The HTTP seam is _common.call, mocked here so no backend is needed.
"""
from __future__ import annotations

import dough_publish


class CallRecorder:
    """Records every call; scripts the GET probe, returns OK for writes."""

    def __init__(self, get_status: int, get_body=None) -> None:
        self.get_status = get_status
        self.get_body = get_body if get_body is not None else {}
        self.calls: list[tuple] = []

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        if method == "GET":
            return self.get_status, self.get_body
        return 200, {"ok": True}

    def write_call(self):
        return next((c for c in self.calls if c[0] in ("POST", "PUT")), None)


def _make_dough(tmp_path, name, dough_yaml, box_yaml=None):
    d = tmp_path / name
    d.mkdir()
    (d / "dough.yaml").write_text(dough_yaml, encoding="utf-8")
    if box_yaml is not None:
        (d / "box.yaml").write_text(box_yaml, encoding="utf-8")
    return d


def test_new_dough_posts_with_labels_and_box(tmp_path, monkeypatch, capsys):
    rec = CallRecorder(get_status=404)
    monkeypatch.setattr(dough_publish, "call", rec)
    d = _make_dough(
        tmp_path, "greeter",
        "id: user.greeter\ninputs:\n  topic:\n    type: string\n",
        "en:\n  name: Greeter\n  about: says hi\n",
    )

    rc = dough_publish.publish(str(d), draft=False)
    assert rc == 0
    method, path, body = rec.write_call()
    assert method == "POST" and path == "/doughs"
    assert body["id"] == "user.greeter"
    assert body["name"] == "Greeter"
    assert body["about"] == "says hi"
    assert "box" in body and dict(body["box"]["en"])["name"] == "Greeter"
    assert '"publish": "created"' in capsys.readouterr().out


def test_existing_dough_puts(tmp_path, monkeypatch):
    rec = CallRecorder(get_status=200)
    monkeypatch.setattr(dough_publish, "call", rec)
    d = _make_dough(tmp_path, "greeter", "id: user.greeter\ninputs: {}\n")

    rc = dough_publish.publish(str(d), draft=False)
    assert rc == 0
    method, path, _ = rec.write_call()
    assert method == "PUT" and path == "/doughs/user.greeter"


def test_draft_flag_adds_query_on_put(tmp_path, monkeypatch):
    rec = CallRecorder(get_status=200)
    monkeypatch.setattr(dough_publish, "call", rec)
    d = _make_dough(tmp_path, "greeter", "id: user.greeter\ninputs: {}\n")

    dough_publish.publish(str(d), draft=True)
    _, path, _ = rec.write_call()
    assert path == "/doughs/user.greeter?draft=true"


def test_id_defaults_to_user_plus_dirname(tmp_path, monkeypatch):
    rec = CallRecorder(get_status=404)
    monkeypatch.setattr(dough_publish, "call", rec)
    d = _make_dough(tmp_path, "myauto", "inputs:\n  x:\n    type: string\n")

    dough_publish.publish(str(d), draft=False)
    _, _, body = rec.write_call()
    assert body["id"] == "user.myauto"
    # the GET probe used the derived id too
    assert rec.calls[0] == ("GET", "/doughs/user.myauto", None)


def test_server_managed_keys_are_stripped(tmp_path, monkeypatch):
    rec = CallRecorder(get_status=404)
    monkeypatch.setattr(dough_publish, "call", rec)
    d = _make_dough(
        tmp_path, "x",
        "id: user.x\nversion: 7\ncreated_at: '2020'\nupdated_at: '2021'\ninputs: {}\n",
    )

    dough_publish.publish(str(d), draft=False)
    _, _, body = rec.write_call()
    for k in ("version", "created_at", "updated_at"):
        assert k not in body


def test_inconclusive_probe_does_not_write(tmp_path, monkeypatch):
    rec = CallRecorder(get_status=503, get_body={"detail": "down"})
    monkeypatch.setattr(dough_publish, "call", rec)
    d = _make_dough(tmp_path, "x", "id: user.x\ninputs: {}\n")

    rc = dough_publish.publish(str(d), draft=False)
    assert rc == 1
    assert rec.write_call() is None  # never fired a doomed POST/PUT
    assert [c[0] for c in rec.calls] == ["GET"]


def test_missing_dough_yaml_reports_error(tmp_path, monkeypatch):
    rec = CallRecorder(get_status=404)
    monkeypatch.setattr(dough_publish, "call", rec)
    empty = tmp_path / "empty"
    empty.mkdir()

    rc = dough_publish.publish(str(empty), draft=False)
    assert rc == 1
    assert rec.calls == []  # bailed before any HTTP
