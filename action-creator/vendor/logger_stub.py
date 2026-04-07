"""Minimal logger stub for vendored action_replay.py.

Replaces app.utils.logger when running outside the backend.
"""

import logging

logger = logging.getLogger("action_creator.vendor")
