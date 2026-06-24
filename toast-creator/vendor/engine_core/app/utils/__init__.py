"""Vendored stub (sync_engine_core.py — do not edit).

The real app/utils/__init__.py re-exports app.utils.logger, which
drags structlog + app.config.settings. Nothing in the offline
validation closure needs the logger; this stub keeps the package
importable without those deps.
"""
