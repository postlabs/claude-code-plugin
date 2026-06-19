"""Regenerate vendor/peel/ — the peel MCP server slice of the Toast backend.

Dev-side script (vendored-MCP-server support). Copies the CURATED SUBSET of
the peel MCP server out of a mojo checkout into <plugin>/vendor/peel/,
preserving the peel/ package structure:

    python scripts/sync_peel.py

Env:
    TOAST_REPO — path to the mojo checkout to vendor from
                 (default C:/Code/mojo/.worktrees/automation-view)

This mirrors sync_engine_core.py: vendor/peel is a SINGLE-DIRECTION copy of
mojo's src/backend/peel/ — mojo is the source of truth, vendor is a pinned
snapshot. NEVER hand-edit vendor/peel/*.py; fix upstream and re-sync, else the
next sync silently clobbers the local change.

Curated SUBSET (not a full mirror) — 8 files copied VERBATIM:

    mcp_server.py + mcp/{__init__,core,find,bake,browse,offers,manual}.py

Deliberately EXCLUDED from the vendored tree:
    - peel.cmd      — the human/CI shell client; the plugin spawns the MCP
      server, not the shell twin.
    - README.md     — upstream docs, not needed at runtime.

The exact subset is not hand-fixed: the PRE-COPY closure guard (below) re-derives
which mcp/ siblings the server actually imports and fails if VERBATIM misses one,
so a newly-wired domain module upstream (as ``manual`` once was) is caught, not
silently dropped.

NEVER overwritten (plugin-owned, not from mojo):
    - run_peel.cmd  — the plugin's own launcher (TOAST_PYTHON resolution).
      mojo's peel.cmd is a DIFFERENT, broader shell client; do not conflate.

Third-party deps of the vendored tree (runtime, not for this sync): mcp,
httpx, httpx-sse. This sync itself is stdlib-only.

Idempotent: wipes vendor/peel/mcp/ + vendor/peel/mcp_server.py and rebuilds
them, then stamps vendor/peel/VERSION.json {mojo_rev, synced_at, files,
excluded, launcher} so the peel slice's provenance is recorded exactly like
engine_core's.

Drift guards:
  1. PRE-COPY import-closure guard — parses upstream mcp_server.py and, for
     every bare `import <name>` whose mojo `mcp/<name>.py` exists, asserts that
     module is in the VERBATIM manifest. If upstream wires a NEW domain module
     into the server, this fails LOUDLY before wiping anything (the subset
     would otherwise import-fail at runtime with a missing sibling).
  2. POST-COPY compile smoke — a clean subprocess byte-compiles every copied
     file (catches a syntax-level break in the snapshot).

Prints a JSON summary. Exit 0 on success, 1 on any failure.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from _common import PLUGIN_ROOT, utf8_io

utf8_io()

VENDOR_DIR = PLUGIN_ROOT / "vendor" / "peel"
DEFAULT_REPO = "C:/Code/mojo/.worktrees/automation-view"

# The curated subset of mojo's src/backend/peel/ — copied byte-for-byte.
VERBATIM: list[str] = [
    "mcp_server.py",
    "mcp/__init__.py",
    "mcp/core.py",
    "mcp/find.py",
    "mcp/bake.py",
    "mcp/browse.py",
    "mcp/capture.py",
    "mcp/offers.py",
    "mcp/manual.py",
    "mcp/questions.py",
]

# Present upstream, deliberately NOT vendored — see module docstring.
EXCLUDED: list[str] = ["peel.cmd", "README.md"]

# Plugin-owned launcher under vendor/peel/ — never wiped, never from mojo.
LAUNCHER = "run_peel.cmd"

# Post-copy smoke: byte-compile every vendored file in a clean subprocess.
SMOKE_SCRIPT = r"""
import json, py_compile, sys

ok, errors = True, []
for path in sys.argv[1:]:
    try:
        py_compile.compile(path, doraise=True)
    except py_compile.PyCompileError as e:
        ok = False
        errors.append(str(e))

if ok:
    print("SMOKE PASS")
else:
    print("SMOKE FAIL\n" + "\n".join(errors))
sys.exit(0 if ok else 1)
"""


def git_rev(repo: Path) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def closure_drift(peel_src: Path) -> list[str]:
    """Return domain modules mcp_server.py imports that are NOT in VERBATIM.

    A bare `import <name>` whose mojo `mcp/<name>.py` exists is a sibling the
    server build needs at runtime. Every such module must be vendored or the
    subset import-fails. Non-empty result = closure drift (fail before wipe).
    """
    server = peel_src / "mcp_server.py"
    tree = ast.parse(server.read_text(encoding="utf-8"), filename=str(server))
    vendored_mcp = {
        rel.split("/", 1)[1][:-3]  # "mcp/core.py" -> "core"
        for rel in VERBATIM if rel.startswith("mcp/") and rel.endswith(".py")
    }
    missing: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if "." in name:
                    continue
                if (peel_src / "mcp" / f"{name}.py").is_file() and name not in vendored_mcp:
                    missing.append(name)
    return sorted(set(missing))


def smoke(copied: list[Path]) -> tuple[bool, str]:
    """Byte-compile the freshly-copied tree in a clean subprocess."""
    fd, path = tempfile.mkstemp(suffix=".py", prefix="peel_smoke_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(SMOKE_SCRIPT)
        proc = subprocess.run(
            [sys.executable, path, *[str(p) for p in copied]],
            capture_output=True, text=True,
            env={**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"},
        )
        ok = proc.returncode == 0 and "SMOKE PASS" in proc.stdout
        return ok, (proc.stdout + proc.stderr).strip()
    finally:
        os.unlink(path)


def main() -> int:
    repo = Path(os.environ.get("TOAST_REPO", DEFAULT_REPO)).resolve()
    peel_src = repo / "src" / "backend" / "peel"
    if not (peel_src / "mcp_server.py").is_file():
        print(json.dumps({"synced": False, "error": (
            f"not a mojo checkout: {peel_src} has no mcp_server.py — set TOAST_REPO")},
            ensure_ascii=False))
        return 1

    missing = [rel for rel in VERBATIM if not (peel_src / rel).is_file()]
    if missing:
        print(json.dumps({"synced": False, "error": (
            "manifest members missing from the checkout (closure drift — "
            f"recompute the manifest): {missing}")}, ensure_ascii=False))
        return 1

    # Drift guard 1 (PRE-COPY): a new domain module wired into the server
    # upstream must not be silently dropped from the subset.
    drift = closure_drift(peel_src)
    if drift:
        print(json.dumps({"synced": False, "error": (
            "mcp_server.py imports domain module(s) not in the VERBATIM "
            f"manifest: {drift} — add them (and their deps) to VERBATIM, or "
            "they will be missing at runtime")}, ensure_ascii=False))
        return 1

    # Idempotent rebuild — wipe ONLY the vendored mcp/ tree + mcp_server.py.
    # run_peel.cmd (plugin-owned) and VERSION.json are left in place.
    mcp_tree = VENDOR_DIR / "mcp"
    if mcp_tree.exists():
        shutil.rmtree(mcp_tree)
    (VENDOR_DIR / "mcp_server.py").unlink(missing_ok=True)

    copied: list[Path] = []
    for rel in VERBATIM:
        dest = VENDOR_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(peel_src / rel, dest)
        copied.append(dest)

    rev = git_rev(repo)

    # Drift guard 2 (POST-COPY): smoke the snapshot BEFORE stamping it — a
    # smoke-failed sync must NOT leave a stamped VERSION.json that looks valid.
    ok, smoke_out = smoke(copied)
    if ok:
        version = {
            "mojo_rev": rev,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "files": VERBATIM,
            "excluded": EXCLUDED,
            "launcher": LAUNCHER,
            "smoke": smoke_out,
        }
        (VENDOR_DIR / "VERSION.json").write_text(
            json.dumps(version, indent=2) + "\n", encoding="utf-8", newline="\n")

    print(json.dumps({
        "synced": ok,
        "vendor_dir": str(VENDOR_DIR),
        "mojo_rev": rev,
        "copied": len(copied),
        "excluded": EXCLUDED,
        "launcher": LAUNCHER,
        "smoke": smoke_out,
    }, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
