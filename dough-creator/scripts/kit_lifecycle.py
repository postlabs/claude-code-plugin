"""Kit lifecycle wrapper — the endpoints peel does NOT expose.

Stdlib only. Talks to the Toast backend's /kits lifecycle API:

    python kit_lifecycle.py install <kit_source_dir>   # bind a kit live + VERIFY it bound
    python kit_lifecycle.py reload <kit_id>            # hot-reload after editing kit Python
    python kit_lifecycle.py uninstall <kit_id>         # unload + remove (non-bundled only)
    python kit_lifecycle.py list                       # installed kits + status

install copies <kit_source_dir> into the ACTIVE profile's doughs tree and binds
its tools immediately, then runs a STRONG verify — a half-loaded kit can return
{"verify":"ok"} on the old "has at least one tool" check while being unusable.
verify_install() requires ALL of (verified 2026-06-24):
  1. the kit is registered in GET /kits with >= 1 tool whose schema is
     populated (empty inputs/outputs == a half-load that bake will reject);
  2. every tool's bundled wrapper flour <kit_id>.<tool> is live in the dough
     registry (GET /doughs/<id> == 200) — the half-load that registers a tool
     but not its flour, so bake fails "dough_not_found";
  3. the kit's source landed on disk under the resolved ACTIVE profile
     (resolve_active_profile, registry↔disk correlation).

Self-heal: install does NOT pop sys.modules, so reinstalling an already-loaded
kit can reimport stale Python and never converge. When verify fails, install
issues POST /kits/<id>/reload (which DOES pop sys.modules[<kit>.*] and reimport
fresh from disk) and re-verifies once. If it still fails it is a backend
half-load/idempotency bug, not a cue to hand-copy the kit across profiles. (The
old "copy the source under every profile" workaround is removed: the active
profile is now resolved authoritatively.)

Prints newline-delimited JSON (one object per line). Exit 0 on success, 1 otherwise.
"""
from __future__ import annotations

import json
import os
import sys

from _common import (
    call,
    list_profiles,
    profiles_root,
    report,
    resolve_active_profile,
    utf8_io,
)

utf8_io()


def _kits_index() -> list | None:
    """The GET /kits list, tolerating both the bare-list and envelope shapes."""
    status, data = call("GET", "/kits")
    if status != 200:
        return None
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("kits"), list):
        return data["kits"]
    return None


def kit_entry(kit_id: str, index: list | None = None) -> dict | None:
    """The GET /kits record for *kit_id*, or None."""
    items = index if index is not None else _kits_index()
    if not isinstance(items, list):
        return None
    for k in items:
        if isinstance(k, dict) and k.get("id") == kit_id:
            return k
    return None


def kit_bound(kit_id: str) -> bool:
    """True when GET /kits shows the kit with at least one tool.

    The minimal "did it register" predicate. Kept as the first gate; the full
    install verify (schema + flours + disk) lives in verify_install().
    """
    kit = kit_entry(kit_id)
    return bool(kit and (kit.get("tools") or kit.get("provides")))


def _tool_names(kit: dict) -> list[str]:
    """Bare tool names from a kit record (tools may be dicts or strings)."""
    names = []
    for t in kit.get("tools") or []:
        if isinstance(t, dict) and isinstance(t.get("name"), str):
            names.append(t["name"])
        elif isinstance(t, str):
            names.append(t)
    return names


def _tool_schema_present(kit: dict) -> bool:
    """True if any tool carries a non-empty inputs/outputs schema.

    A half-load registers tool stubs with empty inputs/outputs ([]); a real
    load fills them. (String-only tool entries carry no schema to inspect.)
    """
    for t in kit.get("tools") or []:
        if isinstance(t, dict):
            ins, outs = t.get("inputs"), t.get("outputs")
            if (isinstance(ins, list) and ins) or (isinstance(outs, list) and outs):
                return True
    return False


def verify_install(kit_id: str) -> tuple[bool, dict]:
    """Strong post-install verify. Returns (ok, checks) — ok iff ALL pass."""
    index = _kits_index()
    kit = kit_entry(kit_id, index)
    tools = _tool_names(kit) if kit else []

    missing_flours = [f"{kit_id}.{name}" for name in tools
                      if call("GET", f"/doughs/{kit_id}.{name}")[0] != 200]

    active, evidence = resolve_active_profile()
    root = profiles_root()
    persisted = [p for p in list_profiles(root)
                 if os.path.isdir(os.path.join(root, p, "doughs", kit_id))] if root else []

    checks = {
        "registered": kit is not None,
        "has_tools": bool(tools),
        "tool_schema_present": bool(kit) and _tool_schema_present(kit),
        "flours_registered": bool(tools) and not missing_flours,
        "flours_missing": missing_flours,
        "active_profile": active,
        "active_profile_evidence": evidence,
        "persisted_profiles": persisted,
        # When the active profile is undetermined, accept persistence on exactly
        # one profile rather than hard-blocking on Fix A's uncertainty.
        "persisted_on_active": (active in persisted) if active else (len(persisted) == 1),
    }
    ok = all((checks["registered"], checks["has_tools"], checks["tool_schema_present"],
              checks["flours_registered"], checks["persisted_on_active"]))
    return ok, checks


def _fail_hint(checks: dict) -> str:
    """Point at the specific half-load mode the checks surfaced."""
    if not checks["registered"]:
        return ("kit did not register in GET /kits at all — install rejected or "
                "the Python failed to import.")
    if not checks["has_tools"]:
        return "kit registered but exposes no tools — its kit.yaml tools / load failed."
    if not checks["tool_schema_present"]:
        return ("tools registered with EMPTY schema — a half-load. The kit Python "
                "imported but the tool signatures did not bind.")
    if checks["flours_missing"]:
        return (f"tools bound but their wrapper flours are NOT in the registry "
                f"({', '.join(checks['flours_missing'])}) — bake will fail "
                "dough_not_found. Backend half-load.")
    if not checks["persisted_on_active"]:
        return (f"kit is not persisted under the active profile "
                f"(active={checks['active_profile']}, on disk in "
                f"{checks['persisted_profiles']}). A profile/sys.path mismatch.")
    return "see checks."


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
        if rc != 0:
            return rc
        kit_id = (data.get("kit") or {}).get("id", "") if isinstance(data, dict) else ""
        if not kit_id:
            print(json.dumps({"verify": "SKIPPED",
                              "hint": "install response carried no kit id to verify."}))
            return 0

        ok, checks = verify_install(kit_id)
        if not ok:
            # Self-heal: force a clean reimport (reload pops sys.modules) and
            # re-verify once — closes the stale-module loop install can't.
            print(json.dumps({"verify": "retry", "action": "reload", "kit": kit_id,
                              "checks": checks}, ensure_ascii=False))
            call("POST", f"/kits/{kit_id}/reload")
            ok, checks = verify_install(kit_id)

        if ok:
            print(json.dumps({"verify": "ok", "kit": kit_id, "checks": checks},
                             ensure_ascii=False))
            return 0
        print(json.dumps({"verify": "FAILED", "kit": kit_id, "checks": checks,
                          "hint": _fail_hint(checks)}, ensure_ascii=False))
        return 1

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
