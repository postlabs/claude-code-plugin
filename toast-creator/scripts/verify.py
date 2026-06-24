"""One-command green check for the toast-creator plugin — no mojo checkout needed.

    python scripts/verify.py

Runs three checks against the SHIPPED plugin (not against an upstream repo) and
exits 1 if any fails:

  1. pytest — the first-party script suite under tests/.
  2. engine_core smoke — imports validate_yaml from the VENDORED slice and
     asserts a clean dough yields no issues, a broken one yields exactly
     ref_no_publisher, and no heavy deps (structlog / app.config / bake engine)
     leaked into the closure. (Reuses sync_engine_core.smoke against the
     existing vendor dir — same check the sync runs post-copy.)
  3. peel closure + compile — asserts the vendored mcp_server.py imports no mcp/
     sibling that isn't vendored, every manifest file is present, and the whole
     peel slice byte-compiles. (Reuses sync_peel.closure_drift / smoke.)

This is the VERIFY step (prove the pins are internally consistent); it is
distinct from sync_engine_core.py / sync_peel.py, which REGENERATE the vendored
trees from a mojo checkout. Run verify in CI or before /publish; run the sync
scripts to move the pins. All checks run even if an earlier one fails, so one
invocation shows the full picture.

Deps: pytest + the vendored-tree runtime deps (pydantic, ruamel.yaml). Exit 0
when every check is green, 1 otherwise.
"""
from __future__ import annotations

import subprocess
import sys

from _common import PLUGIN_ROOT, utf8_io

import sync_engine_core
import sync_peel

utf8_io()

ENGINE_DIR = PLUGIN_ROOT / "vendor" / "engine_core"
PEEL_DIR = PLUGIN_ROOT / "vendor" / "peel"


def _run_pytest() -> tuple[bool, str]:
    # No -q here: pytest.ini already sets addopts=-q; a second -q is -qq, which
    # suppresses the "N passed" tally line this summary wants to surface.
    proc = subprocess.run(
        [sys.executable, "-m", "pytest"],
        cwd=str(PLUGIN_ROOT), capture_output=True, text=True,
    )
    out = (proc.stdout + proc.stderr).strip()
    ok = proc.returncode == 0
    # The pytest tally line ("66 passed in 0.60s"), not the progress-dots line.
    lines = out.splitlines()
    summary = next(
        (ln.strip() for ln in reversed(lines)
         if any(k in ln for k in ("passed", "failed", "error", "no tests ran"))),
        lines[-1].strip() if lines else "",
    )
    return ok, (summary if ok else out)


def _engine_smoke() -> tuple[bool, str]:
    return sync_engine_core.smoke(ENGINE_DIR)


def _peel_checks() -> tuple[bool, str]:
    drift = sync_peel.closure_drift(PEEL_DIR)
    if drift:
        return False, f"vendored mcp_server.py imports non-vendored module(s): {drift}"
    files = [PEEL_DIR / rel for rel in sync_peel.VERBATIM]
    missing = [str(f) for f in files if not f.is_file()]
    if missing:
        return False, f"missing vendored peel files: {missing}"
    return sync_peel.smoke(files)


def main() -> int:
    print("[verify] toast-creator\n")
    checks = (
        ("pytest suite", _run_pytest),
        ("engine_core smoke (vendored slice)", _engine_smoke),
        ("peel closure + compile (vendored slice)", _peel_checks),
    )
    all_ok = True
    for name, fn in checks:
        try:
            ok, detail = fn()
        except Exception as exc:  # a check that raises is a failure, not a crash
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        all_ok = all_ok and ok
        line = f"  {'PASS' if ok else 'FAIL'}  {name}"
        if ok and name.startswith("pytest") and detail:
            line += f"  ({detail})"
        print(line)
        if not ok:
            print("        " + detail.replace("\n", "\n        "))
    print("\n[verify] " + ("ALL GREEN" if all_ok else "FAILED"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
