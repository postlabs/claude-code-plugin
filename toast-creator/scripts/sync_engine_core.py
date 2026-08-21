"""Regenerate vendor/engine_core/ — the offline-validation slice of the Toast dough engine.

Dev-side script (standalone-validation support, 0.5.0). Copies the minimal import
closure of `app.doughs.validation.engine.validate_yaml` out of a mojo checkout
into <plugin>/vendor/engine_core/, preserving the app/ package structure:

    python scripts/sync_engine_core.py

Env:
    TOAST_REPO — path to the mojo checkout to vendor from
                 (default C:/Code/mojo/.worktrees/automation-view)

Closure = 35 files copied VERBATIM + 4 docstring-only STUBS (recomputed 2026-08-21):

    - app/utils/__init__.py — the real one re-exports app.utils.logger, which
      drags structlog + app.config.settings; nothing in the closure needs it.
    - app/doughs/execution/__init__.py — the real one re-exports the bake
      engine (events/run/sink); the closure needs only execution/resolver.py.
    - app/utils/profile/{__init__,owner}.py — Dough.folder defaults to the
      signed-in handle, read off the active profile through the logger and
      the settings. Offline the value is never read back, so a placeholder
      string is enough.

    NEVER copy those verbatim — that reintroduces structlog/app.config and
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

from _common import PLUGIN_ROOT, utf8_io

utf8_io()

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
    # web_dough.py left the engine upstream — the web dough is no longer its own
    # Dough subclass, so models/__init__ stopped importing it. Keeping it here
    # only made the sync refuse to run against any current checkout.
    "app/utils/base_model.py",
    # checks.py now derives an artifact's tier and authorizes against it before
    # applying the rules that depend on it. The policy package is stdlib-only
    # and self-contained, so it joins the closure without dragging anything in.
    "app/policy/__init__.py",
    "app/policy/tier.py",
    "app/policy/capabilities.py",
    "app/policy/decide.py",
    # rules.py reads a dough's handle out of its path.
    "app/utils/idpath.py",
    # A dough's view is validated against the spread block catalog now, so the
    # spread slice came along with it. Self-contained: model/catalog/refs plus
    # the spark sub-package, no logger and no settings.
    "app/spreads/__init__.py",
    "app/spreads/model.py",
    "app/spreads/catalog.py",
    "app/spreads/refs.py",
    "app/spreads/validate.py",
    "app/spreads/viewops.py",
    "app/spreads/spark/__init__.py",
    "app/spreads/spark/model.py",
    "app/spreads/spark/anchor.py",
    "app/spreads/spark/capability.py",
    "app/spreads/spark/validate.py",
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
    "app/utils/profile/__init__.py": (
        '"""Vendored stub (sync_engine_core.py — do not edit)."""\n'
    ),
    "app/utils/profile/owner.py": (
        '"""Vendored stub (sync_engine_core.py — do not edit).\n'
        "\n"
        "``Dough.folder`` defaults to the signed-in account's handle, which the\n"
        "real module reads out of the active profile on disk — through the\n"
        "logger and the settings, the two things this slice exists to avoid.\n"
        "Validation never reads the value back (``folder`` is re-derived from\n"
        "the path at load and is not persisted), so offline it only has to be\n"
        'a string.\n"""\n'
        "\n"
        "from __future__ import annotations\n"
        "\n"
        "\n"
        "def active_handle() -> str:\n"
        '    """The placeholder authoring root used when no profile is present."""\n'
        '    return "user"\n'
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
    "path": "user.smoke_clean",
    "inputs": {"topic": {"type": "string", "required": True}},
    "steps": [{"dough": "user.helper", "with": {"q": "${inputs.topic}"}}],
    "return": {"result": "${helper}"},
}
BROKEN = {
    "path": "user.smoke_broken",
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
        dest = VENDOR_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(backend / rel, dest)
        files.append(rel)

    for rel, body in STUBS.items():
        dest = VENDOR_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body, encoding="utf-8", newline="\n")

    rev = git_rev(repo)

    # Smoke the freshly-rebuilt tree BEFORE stamping it — a smoke-failed sync
    # must NOT leave a stamped VERSION.json that offline_validate would trust.
    ok, smoke_out = smoke(VENDOR_DIR)
    if ok:
        version = {
            "mojo_rev": rev,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "files": files,
            "stubs": sorted(STUBS),
            "smoke": smoke_out,
        }
        (VENDOR_DIR / "VERSION.json").write_text(
            json.dumps(version, indent=2) + "\n", encoding="utf-8", newline="\n")

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
