"""Shared test setup for the toast-creator first-party scripts.

The scripts are written to run as ``python scripts/<name>.py`` with the scripts
dir on ``sys.path[0]`` (so ``import _common`` resolves). Tests reproduce that by
putting the scripts dir on the path here, before any test module imports its
target.

Each script calls ``_common.utf8_io()`` at import time, which reconfigures
sys.stdout/stderr to UTF-8 — under pytest's capture those streams may not expose
``.reconfigure``. Neutralise it once, here, BEFORE the target modules bind the
name via ``from _common import ..., utf8_io``. This touches the test process
only; shipped behaviour is unchanged.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import _common  # noqa: E402  — after the path insert

_common.utf8_io = lambda: None  # no-op for the module-level calls in every script
