"""Preflight for dough-creator: is the Toast backend up, and where do doughs live?

Stdlib only — runs on any Python 3. Prints a single JSON object:

    {
      "backend_up": true,
      "base_url": "http://127.0.0.1:18587/api/v1",
      "doughs_dir": "C:\\Users\\me\\AppData\\Roaming\\Toast\\profiles\\local\\doughs",
      "user_doughs_dir": "...\\doughs\\user"
    }

Resolution order for the doughs dir:
  1. TOAST_DOUGHS_DIR env var (explicit override)
  2. %APPDATA%/Toast/profiles/local/doughs   (installed app, current brand)
  3. %APPDATA%/Mojo/profiles/local/doughs    (pre-rebrand installs)

Exit code 0 when the backend is reachable, 1 when it is not (the creator
must stop and tell the user to start Toast).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = os.environ.get("PEEL_BASE_URL", "http://127.0.0.1:18587/api/v1")
HEALTH_URL = BASE_URL.rsplit("/api/", 1)[0] + "/health"


def backend_up() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=3) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def doughs_dir() -> str | None:
    override = os.environ.get("TOAST_DOUGHS_DIR")
    if override and os.path.isdir(override):
        return override
    appdata = os.environ.get("APPDATA", "")
    for brand in ("Toast", "Mojo"):
        cand = os.path.join(appdata, brand, "profiles", "local", "doughs")
        if os.path.isdir(cand):
            return cand
    return None


def main() -> int:
    up = backend_up()
    d = doughs_dir()
    print(json.dumps({
        "backend_up": up,
        "base_url": BASE_URL,
        "doughs_dir": d,
        "user_doughs_dir": os.path.join(d, "user") if d else None,
    }))
    return 0 if up else 1


if __name__ == "__main__":
    sys.exit(main())
