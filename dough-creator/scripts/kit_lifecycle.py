"""Kit lifecycle wrapper — the endpoints peel does NOT expose.

Stdlib only. Talks to the Toast backend's /kits lifecycle API:

    python kit_lifecycle.py install <kit_source_dir>   # bind a kit live + VERIFY it bound
    python kit_lifecycle.py reload <kit_id>            # hot-reload after editing kit Python
    python kit_lifecycle.py uninstall <kit_id>         # unload + remove (non-bundled only)
    python kit_lifecycle.py list                       # installed kits + status

install copies <kit_source_dir> into the ACTIVE profile's doughs tree and binds
its tools immediately, then VERIFIES the kit appears in GET /kits with tools —
because a 400 "Failed to load kit" or a kit that indexes but doesn't bind
usually means ONE root cause (verified 2026-06-11): the backend's active
profile differs from the one whose doughs dir is on sys.path, so the kit's
Python cannot import. Symptoms that all share this cause:
  - 400 {"detail": "Failed to load kit — check kit.yaml"}
  - bake fails "Tool not found: '<kit>.<tool>' — no kit registered"
  - reload fails "Kit not found"
Workaround when it happens: copy the kit source under EVERY
{profiles}/<key>/doughs/<kit_id>/ (toast_env.py lists the profiles), then
install again.

Prints newline-delimited JSON (one object per line). Exit 0 on success, 1 otherwise.
"""
from __future__ import annotations

import json
import os
import sys

from _common import call, report, utf8_io

utf8_io()


def kit_bound(kit_id: str) -> bool:
    """True when GET /kits shows the kit with at least one tool."""
    status, data = call("GET", "/kits")
    if status != 200 or not isinstance(data, (list, dict)):
        return False
    items = data if isinstance(data, list) else data.get("kits", [])
    for k in items:
        if isinstance(k, dict) and k.get("id") == kit_id:
            return bool(k.get("tools") or k.get("provides"))
    return False


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]

    if cmd == "install":
        if len(sys.argv) < 3:
            print(__doc__)
            return 2
        kit_dir = os.path.abspath(sys.argv[2])
        status, data = call("POST", "/kits/install", {"path": kit_dir})
        rc = report(status, data)
        if rc == 0:
            kit_id = ""
            if isinstance(data, dict):
                kit_id = (data.get("kit") or {}).get("id", "")
            if kit_id and not kit_bound(kit_id):
                print(json.dumps({"verify": "FAILED", "hint": (
                    f"kit '{kit_id}' installed but its tools are NOT bound — "
                    "active-profile/sys.path mismatch. Copy the kit source under "
                    "every {profiles}/<key>/doughs/<kit_id>/ (see toast_env.py "
                    "profiles list) and install again.")}, ensure_ascii=False))
                return 1
            print(json.dumps({"verify": "ok", "kit": kit_id}))
        return rc

    if cmd == "reload":
        if len(sys.argv) < 3:
            print(__doc__)
            return 2
        status, data = call("POST", f"/kits/{sys.argv[2]}/reload")
        return report(status, data)
    if cmd == "uninstall":
        if len(sys.argv) < 3:
            print(__doc__)
            return 2
        status, data = call("DELETE", f"/kits/{sys.argv[2]}")
        return report(status, data)
    if cmd == "list":
        status, data = call("GET", "/kits")
        return report(status, data)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
