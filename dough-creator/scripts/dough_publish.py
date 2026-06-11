"""User-dough publishing over the Toast dough CRUD API — cwd is the source of truth.

v0.3: the plugin NEVER writes into Toast profile directories. User doughs are
authored under the session cwd and published through the API:

    python dough_publish.py publish <dough_dir> [--draft]   # POST new / PUT existing
    python dough_publish.py pull <dough_id> <dest_dir>      # materialize into cwd
    python dough_publish.py delete <dough_id>               # remove from backend

publish reads <dough_dir>/dough.yaml + box.yaml, builds the payload, checks
existence via GET /doughs/{id}, then POST /doughs (new) or PUT /doughs/{id}
(existing; ?draft=true with --draft). A 422 body carries validation_errors —
publishing IS validation; they are printed verbatim.

LABEL CAVEAT (verified 2026-06-11): the CRUD API persists only en.name +
en.about — sent as TOP-LEVEL payload extras "name"/"about" — and only at
CREATION (box.yaml is seeded once; PUT never touches it). Per-input/output
descriptions and non-en locales are dropped server-side. The full box is still
sent under a "box" key (ignored today, future-proof) so the cwd source stays
the single source of truth.

pull GETs /doughs/retrieval/spec/{id} — parsed dough.yaml as JSON plus a "box"
key bundling box.yaml with all on-disk locales — and writes dough.yaml +
box.yaml into <dest_dir> (the modify flow: pull -> edit -> publish).

Requires ruamel.yaml — run with the embedded Toast Python (the interpreter
peel uses), e.g. <mojo repo>/src/extraResources/python/win32-x64/python/python.exe,
or any Python with `pip install ruamel.yaml`.

Prints the JSON response body. Exit 0 on success, 1 otherwise.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

# Never die on console codepage (cp949) — error bodies may carry UTF-8.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from ruamel.yaml import YAML
except ImportError:
    print(json.dumps({"status": 0, "body": {"error": (
        "ruamel.yaml is not installed in this interpreter — run dough_publish.py "
        "with the embedded Toast Python (the same interpreter peel uses), e.g. "
        "<mojo repo>/src/extraResources/python/win32-x64/python/python.exe, "
        "or `pip install ruamel.yaml`.")}}, ensure_ascii=False))
    sys.exit(1)

BASE_URL = os.environ.get("PEEL_BASE_URL", "http://127.0.0.1:18587/api/v1")

# Server-managed keys — never round-tripped from/to the payload.
SERVER_KEYS = ("version", "created_at", "updated_at")

_yaml = YAML()
_yaml.default_flow_style = False
_yaml.allow_unicode = True
_yaml.width = 4096


def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict | str]:
    req = urllib.request.Request(
        BASE_URL + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(text)
        except ValueError:
            return e.code, text
    except (urllib.error.URLError, OSError) as e:
        return 0, {"error": f"backend unreachable: {e}"}
    try:
        return 200, json.loads(text)
    except ValueError:
        return 200, text


def report(status: int, data) -> int:
    print(json.dumps({"status": status, "body": data}, ensure_ascii=False))
    return 0 if 200 <= status < 300 else 1


def load_yaml(path: str):
    with open(path, encoding="utf-8") as f:
        return _yaml.load(f)


def dump_yaml(path: str, data) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        _yaml.dump(data, f)


def print_validation_errors(status: int, data) -> None:
    """On 422 surface validation_errors verbatim — publishing IS validation."""
    if status != 422 or not isinstance(data, dict):
        return
    errs = data.get("validation_errors")
    if errs is None and isinstance(data.get("detail"), dict):
        errs = data["detail"].get("validation_errors")
    if errs is not None:
        print(json.dumps({"validation_errors": errs}, ensure_ascii=False))


def publish(dough_dir: str, draft: bool) -> int:
    dough_dir = os.path.abspath(dough_dir)
    dough_path = os.path.join(dough_dir, "dough.yaml")
    box_path = os.path.join(dough_dir, "box.yaml")
    if not os.path.isfile(dough_path):
        return report(0, {"error": f"no dough.yaml under {dough_dir}"})
    dough = load_yaml(dough_path) or {}
    box = (load_yaml(box_path) or {}) if os.path.isfile(box_path) else {}

    payload = {k: v for k, v in dough.items() if k not in SERVER_KEYS}
    dough_id = payload.get("id") or "user." + os.path.basename(dough_dir)
    payload["id"] = dough_id
    en = box.get("en") or {}
    # Top-level name/about extras are the ONLY labels the API persists (en, creation-only).
    if en.get("name"):
        payload["name"] = en["name"]
    if en.get("about"):
        payload["about"] = en["about"]
    if box:
        payload["box"] = box  # ignored by the backend today; kept for a future write path

    exists, _ = call("GET", f"/doughs/{dough_id}")
    if exists == 200:
        query = "?draft=true" if draft else ""
        status, data = call("PUT", f"/doughs/{dough_id}{query}", payload)
        verb = "updated"
    else:
        status, data = call("POST", "/doughs", payload)
        verb = "created"
    rc = report(status, data)
    print_validation_errors(status, data)
    if rc == 0:
        print(json.dumps({"publish": verb, "dough": dough_id, "source": dough_dir},
                         ensure_ascii=False))
    return rc


def pull(dough_id: str, dest_dir: str) -> int:
    status, data = call("GET", f"/doughs/retrieval/spec/{dough_id}")
    if status != 200 or not isinstance(data, dict):
        return report(status, data)
    spec = dict(data)
    box = spec.pop("box", None) or {}
    for key in SERVER_KEYS:
        spec.pop(key, None)
    dest_dir = os.path.abspath(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)
    dump_yaml(os.path.join(dest_dir, "dough.yaml"), spec)
    dump_yaml(os.path.join(dest_dir, "box.yaml"), box)
    print(json.dumps({"status": status, "body": {
        "pulled": dough_id,
        "dir": dest_dir,
        "files": ["dough.yaml", "box.yaml"],
        "locales": sorted(box.keys()) if isinstance(box, dict) else [],
    }}, ensure_ascii=False))
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]

    if cmd == "publish" and len(sys.argv) >= 3:
        return publish(sys.argv[2], draft="--draft" in sys.argv[3:])
    if cmd == "pull" and len(sys.argv) >= 4:
        return pull(sys.argv[2], sys.argv[3])
    if cmd == "delete" and len(sys.argv) >= 3:
        status, data = call("DELETE", f"/doughs/{sys.argv[2]}")
        return report(status, data)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
