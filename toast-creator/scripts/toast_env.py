"""Preflight for toast-creator: detect the run tier.

Stdlib only — runs on any Python 3. Prints a single JSON object:

    {
      "backend_up": true,
      "tier": "connected",
      "base_url": "http://127.0.0.1:18587/api/v1",
      "diagnostics": {
        "profiles": ["local", "5ca3000af7e4"],
        "active_profile": "5ca3000af7e4",
        "active_profile_evidence": {"method": "registry_disk_correlation", ...},
        "active_profile_ambiguous": false,
        "doughs_dirs": {"local": "...\\profiles\\local\\doughs", ...}
      }
    }

backend_up + tier + base_url are the contract. "tier" is "connected" when
the Toast backend answers /health, "standalone" when it does not.
Standalone is a SUPPORTED tier, not a failure: the creator continues with
offline validation + direct tool unit runs and DEFERS publish/bake (see
commands/create.md, step 0 Preflight). The plugin NEVER writes into
profile directories by path — cwd is the source of truth: user doughs go
through dough_publish.py (API), kits through kit_lifecycle.py install (API).

The "diagnostics" block exists ONLY for the kit-install troubleshooting path.
ACTIVE PROFILE (verified 2026-06-24): the backend resolves the active profile
server-side from the logged-in session (a JWT-derived key like 5ca3000af7e4,
NOT "local" when signed in) and exposes it through NO API. But it is still
knowable without guessing: the live GET /doughs registry IS the active
profile's on-disk content, so the profile whose doughs/ tree covers that id set
is the active one — the same profile dough_publish.py / kit install write to.
``active_profile`` reports that correlation; ``active_profile_ambiguous`` is
true ONLY when the correlation genuinely cannot decide (backend down, no
profiles, or a real tie) — it is NOT raised merely because >1 profile dir
exists. Do NOT hand-copy kits across every profile on the strength of this
block; that footgun is gone (see commands/test.md and kit_lifecycle.py).

Resolution order for the profiles root (diagnostics only):
  1. TOAST_PROFILES_DIR env var (explicit override)
  2. %APPDATA%/Toast/profiles   (installed app, current brand)
  3. %APPDATA%/Mojo/profiles    (pre-rebrand installs)

Exit code 0 in BOTH tiers (standalone is not an error); 1 only on
unexpected internal errors.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from _common import (
    BASE_URL,
    list_profiles,
    profiles_root,
    resolve_active_profile,
    utf8_io,
)

utf8_io()

HEALTH_URL = BASE_URL.rsplit("/api/", 1)[0] + "/health"


def backend_up() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=3) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def main() -> int:
    up = backend_up()
    root = profiles_root()
    profiles = list_profiles(root)
    doughs = {p: os.path.join(root, p, "doughs") for p in profiles} if root else {}

    # The active profile is correlation-knowable only when the backend is up to
    # answer GET /doughs. Standalone defers publish/bake, so it is moot there.
    active, evidence = (resolve_active_profile(root, profiles)
                        if up else (None, {"method": "registry_disk_correlation",
                                           "reason": "standalone"}))

    print(json.dumps({
        "backend_up": up,
        "tier": "connected" if up else "standalone",
        "base_url": BASE_URL,
        "diagnostics": {
            "profiles": profiles,
            "active_profile": active,
            "active_profile_evidence": evidence,
            # True only when we ARE connected, there is something to choose, and
            # the authoritative correlation still could not decide. Never a bare
            # "more than one profile dir exists" guess.
            "active_profile_ambiguous": up and active is None and len(profiles) > 1,
            "doughs_dirs": doughs,
        },
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # unexpected only — tier detection never raises
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
        sys.exit(1)
