"""Regenerate vendor/engine_core/ — the offline-validation slice of the Toast dough engine.

Dev-side script (Tier-1 "standalone" support, v0.4). Copies the minimal import
closure of `app.doughs.validation.engine.validate_yaml` out of a mojo checkout
into <plugin>/vendor/engine_core/, preserving the app/ package structure:

    python scripts/sync_engine_core.py

Env:
    TOAST_REPO — path to the mojo checkout to vendor from
                 (default C:/Code/mojo/.worktrees/automation-view)

Closure = 19 files copied VERBATIM + 2 docstring-only STUBS (proven 2026-06-11):

    - app/utils/__init__.py — the real one re-exports app.utils.logger, which
      drags structlog + app.config.settings; nothing in the closure needs it.
    - app/doughs/execution/__init__.py — the real one re-exports the bake
      engine (events/run/sink); the closure needs only execution/resolver.py.

    NEVER copy those two verbatim — that reintroduces structlog/app.config and
    the whole bake engine into the vendored tree.

Third-party deps of the vendored tree: pydantic ONLY (callers additionally
need ruamel.yaml to parse YAML before calling validate_yaml).

Idempotent: wipes vendor/engine_core/app/ and rebuilds it, then stamps
vendor/engine_core/VERSION.json {mojo_rev, synced_at, files, stubs} so
provenance records can name the engine slice that validated each artifact.

Verification step (the drift guard): after copying, a subprocess smoke-imports
validate_yaml from the vendored tree (vendor path first on sys.path), checks a
broken dough yields exactly ref_no_publisher, a clean dough yields zero issues,
and that no heavy modules (structlog / app.config / app.kits / bake engine)
were pulled in. New imports added upstream to any closure member would
silently break the vendored tree — this smoke is what catches that.

Run with a Python that has pydantic (e.g. the embedded Toast interpreter:
<mojo repo>/src/extraResources/python/win32-x64/python/python.exe).

Prints a JSON summary. Exit 0 on success, 1 on any failure.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Never die on console codepage (cp949) — paths/messages may carry UTF-8.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = PLUGIN_ROOT / "vendor" / "engine_core"
DEFAULT_REPO = "C:/Code/mojo/.worktrees/automation-view"

# The proven minimal closure of `from app.doughs.validation.engine import
# validate_yaml` — copied byte-for-byte from <repo>/src/backend/.
VERBATIM: list[str] = [
    "app/__init__.py",
    "app/doughs/__init__.py",
    "app/doughs/validation/__init__.py",
    "app/doughs/validation/engine.py",
    "app/doughs/validation/checks.py",
    "app/doughs/validation/drill.py",
    "app/doughs/validation/rules.py",
    "app/doughs/definitions/__init__.py",
    "app/doughs/definitions/ids.py",
    "app/doughs/execution/resolver.py",
    "app/doughs/models/__init__.py",
    "app/doughs/models/enums.py",
    "app/doughs/models/ports.py",
    "app/doughs/models/box.py",
    "app/doughs/models/steps.py",
    "app/doughs/models/dough.py",
    "app/doughs/models/donut.py",
    "app/doughs/models/web_dough.py",
    "app/utils/base_model.py",
]

# Docstring-only stubs — see module docstring for why these two MUST be
# stubbed, never copied.
STUBS: dict[str, str] = {
    "app/utils/__init__.py": (
        '"""Vendored stub (sync_engine_core.py — do not edit).\n'
        "\n"
        "The real app/utils/__init__.py re-exports app.utils.logger, which\n"
        "drags structlog + app.config.settings. Nothing in the offline\n"
        "validation closure needs the logger; this stub keeps the package\n"
        'importable without those deps.\n"""\n'
    ),
    "app/doughs/execution/__init__.py": (
        '"""Vendored stub (sync_engine_core.py — do not edit).\n'
        "\n"
        "The real app/doughs/execution/__init__.py re-exports the bake engine\n"
        "(events / run / sink). The offline validation closure needs only\n"
        'execution/resolver.py (stdlib-only REF_PATTERN).\n"""\n'
    ),
}

# Subprocess smoke run after every sync — the drift guard.
SMOKE_SCRIPT = r"""
import json, os, sys

vendor = os.path.realpath(sys.argv[1])
sys.path.insert(0, vendor)

import app
assert os.path.realpath(app.__file__).startswith(vendor), (
    "app resolved outside the vendor tree: " + app.__file__)

from app.doughs.validation.engine import validate_yaml

CLEAN = {
    "id": "user.smoke_clean",
    "inputs": {"topic": {"type": "string", "required": True}},
    "steps": [{"dough": "user.helper", "with": {"q": "${inputs.topic}"}}],
    "return": {"result": "${helper}"},
}
BROKEN = {
    "id": "user.smoke_broken",
    "inputs": {"topic": {"type": "string", "required": True}},
    "steps": [{"dough": "user.helper", "with": {"q": "${nonexistent.value}"}}],
    "return": {"result": "${helper}"},
}

clean_issues = validate_yaml(CLEAN)
broken_issues = validate_yaml(BROKEN)
assert clean_issues == [], json.dumps([i.to_dict() for i in clean_issues])
assert [i.code for i in broken_issues] == ["ref_no_publisher"], (
    json.dumps([i.to_dict() for i in broken_issues]))

heavy = [m for m in (
    "structlog", "app.utils.logger", "app.config", "app.kits",
    "app.doughs.execution.events", "app.doughs.execution.run",
    "app.doughs.execution.sink",
) if m in sys.modules]
assert not heavy, "heavy modules leaked into the closure: %r" % heavy

print("SMOKE PASS")
"""


def git_rev(repo: Path) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def smoke(vendor_dir: Path) -> tuple[bool, str]:
    """Run the vendored-tree smoke in a clean subprocess."""
    fd, path = tempfile.mkstemp(suffix=".py", prefix="engine_core_smoke_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(SMOKE_SCRIPT)
        proc = subprocess.run(
            [sys.executable, path, str(vendor_dir)],
            capture_output=True, text=True,
            # PYTHONDONTWRITEBYTECODE keeps __pycache__ out of the vendor tree.
            env={**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"},
        )
        ok = proc.returncode == 0 and "SMOKE PASS" in proc.stdout
        return ok, (proc.stdout + proc.stderr).strip()
    finally:
        os.unlink(path)


def main() -> int:
    repo = Path(os.environ.get("TOAST_REPO", DEFAULT_REPO)).resolve()
    backend = repo / "src" / "backend"
    if not (backend / "app" / "doughs" / "validation" / "engine.py").is_file():
        print(json.dumps({"synced": False, "error": (
            f"not a mojo checkout: {backend} has no "
            "app/doughs/validation/engine.py — set TOAST_REPO")},
            ensure_ascii=False))
        return 1

    missing = [rel for rel in VERBATIM if not (backend / rel).is_file()]
    if missing:
        print(json.dumps({"synced": False, "error": (
            "closure members missing from the checkout (closure drift — "
            f"recompute the manifest): {missing}")}, ensure_ascii=False))
        return 1

    # Idempotent rebuild — wipe the app/ tree so removed files don't linger.
    app_tree = VENDOR_DIR / "app"
    if app_tree.exists():
        shutil.rmtree(app_tree)

    files: list[str] = []
    for rel in VERBATIM:
        if rel in STUBS:  # belt-and-braces: stubs always win over copies
            continue
        dest = VENDOR_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(backend / rel, dest)
        files.append(rel)

    for rel, body in STUBS.items():
        dest = VENDOR_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body, encoding="utf-8", newline="\n")

    rev = git_rev(repo)
    version = {
        "mojo_rev": rev,
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
        "stubs": sorted(STUBS),
    }
    (VENDOR_DIR / "VERSION.json").write_text(
        json.dumps(version, indent=2) + "\n", encoding="utf-8", newline="\n")

    ok, smoke_out = smoke(VENDOR_DIR)
    print(json.dumps({
        "synced": ok,
        "vendor_dir": str(VENDOR_DIR),
        "mojo_rev": rev,
        "copied": len(files),
        "stubbed": sorted(STUBS),
        "smoke": smoke_out,
    }, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
