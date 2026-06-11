"""Kit lifecycle wrapper — the endpoints peel does NOT expose.

Stdlib only. Talks to the Toast backend's /kits lifecycle API
(src/backend/app/kits/api/lifecycle.py in the Toast repo):

    python kit_lifecycle.py install <kit_source_dir>   # bind a kit live (no restart)
    python kit_lifecycle.py reload <kit_id>            # hot-reload after editing tools.py
    python kit_lifecycle.py uninstall <kit_id>         # unload + remove (non-bundled only)
    python kit_lifecycle.py list                       # installed kits + status

install copies <kit_source_dir> into {profile}/doughs/<kit.id>/ and binds its
tools immediately. reload pops the kit's modules and re-imports from disk —
the edit-test loop never needs a backend restart. Caveat: a failed reload
leaves the kit UNLOADED; fix the import error and reload again.

Prints the JSON response body. Exit 0 on 2xx, 1 otherwise.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = os.environ.get("PEEL_BASE_URL", "http://127.0.0.1:18587/api/v1")


def call(method: str, path: str, body: dict | None = None) -> int:
    req = urllib.request.Request(
        BASE_URL + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            print(resp.read().decode("utf-8", errors="replace"))
            return 0
    except urllib.error.HTTPError as e:
        print(e.read().decode("utf-8", errors="replace"))
        return 1
    except (urllib.error.URLError, OSError) as e:
        print(json.dumps({"error": f"backend unreachable: {e}"}))
        return 1


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    if cmd == "install":
        return call("POST", "/kits/install", {"path": os.path.abspath(sys.argv[2])})
    if cmd == "reload":
        return call("POST", f"/kits/{sys.argv[2]}/reload")
    if cmd == "uninstall":
        return call("DELETE", f"/kits/{sys.argv[2]}")
    if cmd == "list":
        return call("GET", "/kits")
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
