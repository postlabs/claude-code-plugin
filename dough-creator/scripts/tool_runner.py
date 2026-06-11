"""Tier-1 unit-verification harness — run ONE kit tool directly, no Toast backend.

    python tool_runner.py <kit_dir> <symbol_or_entry> [--inputs <json or @file.json>]

Examples:
    python tool_runner.py ./my_kit fetch_price --inputs '{"symbol": "BTCUSDT"}'
    python tool_runner.py ./my_kit levels.py:find_levels --inputs @inputs.json
    python tool_runner.py ./my_kit save_note          # symbol resolved via flour entry: scan

What this proves / does NOT prove:
  PROVES   the tool's Python logic runs and returns a sane value with the
           given inputs (Tier-1 "unit-verified" provenance).
  DOES NOT prove engine binding — flour entry: wiring, input/output schema
           conformance, box.yaml, or that the kit loads in Toast. Those are
           Tier-2 (kit_lifecycle.py install + real bake).

Mechanics:
  1. sys.path gets vendor/core_stub prepended, so `from _core.profile import
     profile_dir` etc. resolve to the standalone stub (file store under
     $TOAST_STORE_DIR, default ./.toast_store) instead of Toast's _core.
  2. sys.path gets the PARENT of <kit_dir> prepended, so the kit's own
     absolute imports (`from <kit_folder>.expr import ...`) resolve. The kit
     folder name must equal the kit id (true for single-segment ids).
  3. Symbol resolution, in order:
       - explicit entry form `<file>.py:<symbol>` — import that module;
       - bare symbol — try `tools.py:<symbol>` (the default convention);
       - fall back to scanning `*/dough.yaml` for a matching
         `entry: <file>.py:<symbol>` line.
  4. The tool is called with **inputs; coroutines are driven via
     asyncio.run(). Pydantic results are serialized with model_dump().

Output: one JSON object on stdout —
    {"ok": true,  "result": ..., "tool": "<module>:<symbol>"}
    {"ok": false, "error": "...", "traceback": "..."}
Exit 0 on success, 1 on tool/import failure, 2 on usage error.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import inspect
import json
import re
import sys
import traceback
from pathlib import Path
from typing import Any

# Never die on console codepage (cp949) — results may carry UTF-8.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Keep vendor/core_stub (and the user's kit source) free of __pycache__.
sys.dont_write_bytecode = True

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
CORE_STUB_DIR = PLUGIN_ROOT / "vendor" / "core_stub"

# `entry: <file>.py:<symbol>` line in a flour dough.yaml (no yaml dep needed).
_ENTRY_RE = re.compile(r"^entry:\s*([\w.]+\.py)\s*:\s*(\w+)\s*$", re.MULTILINE)


def _parse_inputs(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    if raw.startswith("@"):
        raw = Path(raw[1:]).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("--inputs must be a JSON object (tool kwargs)")
    return data


def _scan_flour_entries(kit_dir: Path, symbol: str) -> str | None:
    """Find `entry: <file>.py:<symbol>` across the kit's flour dough.yaml files."""
    for dough_yaml in sorted(kit_dir.glob("*/dough.yaml")):
        try:
            text = dough_yaml.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in _ENTRY_RE.finditer(text):
            if m.group(2) == symbol:
                return m.group(1)
    return None


def _resolve(kit_dir: Path, spec: str) -> tuple[Any, str]:
    """Return (callable, '<module_file>:<symbol>') for a symbol-or-entry spec."""
    if ":" in spec:
        file_part, symbol = spec.split(":", 1)
        if not file_part.endswith(".py"):
            raise ValueError(f"entry form must be <file>.py:<symbol>, got {spec!r}")
    else:
        symbol = spec
        file_part = "tools.py"
        has_default = (kit_dir / "tools.py").exists()
        scanned = None
        if not has_default:
            scanned = _scan_flour_entries(kit_dir, symbol)
            if scanned is None:
                raise ImportError(
                    f"no tools.py in {kit_dir} and no flour dough.yaml declares "
                    f"`entry: <file>.py:{symbol}` — pass the explicit "
                    f"<file>.py:{symbol} form"
                )
            file_part = scanned

    module_name = f"{kit_dir.name}.{file_part[:-3]}"
    try:
        mod = importlib.import_module(module_name)
    except ImportError:
        raise
    try:
        fn = getattr(mod, symbol)
    except AttributeError:
        # Bare symbol that defaulted to tools.py but lives elsewhere: scan.
        if ":" not in spec:
            scanned = _scan_flour_entries(kit_dir, symbol)
            if scanned and scanned != file_part:
                mod = importlib.import_module(f"{kit_dir.name}.{scanned[:-3]}")
                fn = getattr(mod, symbol)
                return fn, f"{scanned}:{symbol}"
        raise
    return fn, f"{file_part}:{symbol}"


def _jsonable(obj: Any) -> Any:
    """json.dumps default= hook: pydantic models, paths, sets, the rest str()."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, (set, frozenset)):
        return sorted(obj, key=str)
    return str(obj)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="tool_runner.py",
        description="Run one kit tool directly (Tier-1, no Toast backend).",
    )
    parser.add_argument("kit_dir", help="kit source dir (folder name = kit id)")
    parser.add_argument("symbol", help="<symbol> (default tools.py) or <file>.py:<symbol>")
    parser.add_argument("--inputs", default=None, help="JSON object or @file.json")
    args = parser.parse_args()

    kit_dir = Path(args.kit_dir).resolve()
    if not kit_dir.is_dir():
        print(json.dumps({"ok": False, "error": f"kit_dir not found: {kit_dir}"}))
        return 2
    try:
        inputs = _parse_inputs(args.inputs)
    except (ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "error": f"bad --inputs: {exc}"}))
        return 2

    # Stub _core first, then the kit's parent so `import <kit>.<module>` works.
    sys.path.insert(0, str(CORE_STUB_DIR))
    sys.path.insert(0, str(kit_dir.parent))

    try:
        fn, tool_ref = _resolve(kit_dir, args.symbol)
        if not callable(fn):
            raise TypeError(f"{tool_ref} resolved to non-callable {type(fn).__name__}")
        if inspect.iscoroutinefunction(fn):
            result = asyncio.run(fn(**inputs))
        else:
            result = fn(**inputs)
            if inspect.iscoroutine(result):
                result = asyncio.run(result)
    except Exception as exc:
        print(json.dumps({
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }, ensure_ascii=False))
        return 1

    print(json.dumps(
        {"ok": True, "result": result, "tool": tool_ref},
        ensure_ascii=False,
        default=_jsonable,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
