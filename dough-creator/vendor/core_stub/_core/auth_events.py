"""Connect-flow event types — standalone stub of the real ``_core.auth_events``.

Verbatim copy of the real module's dataclasses + factories (stdlib
``dataclasses`` only, no pydantic): kit ``connect.py`` modules import
these at module top, so even though Tier-1 unit runs never *call* the
connect flow, the symbols must exist for any kit module that happens to
import them transitively. Events are plain dataclasses with
``to_dict()`` — dict-like enough for offline inspection; there is no
SSE stream standalone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AuthStatus:
    """Result of a non-interactive auth check."""

    authenticated: bool
    method: str | None = None
    user_info: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"authenticated": self.authenticated}
        if self.method:
            d["method"] = self.method
        if self.user_info:
            d["user_info"] = self.user_info
        if self.error:
            d["error"] = self.error
        return d


@dataclass
class AuthEvent:
    """Event emitted during connect()."""

    event: str
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"event": self.event, "data": self.data}


def auth_started(provider: str, **kw: Any) -> AuthEvent:
    return AuthEvent(event="started", data={"provider": provider, **kw})


def auth_waiting(provider: str, message: str = "", **kw: Any) -> AuthEvent:
    return AuthEvent(event="waiting", data={"provider": provider, "message": message, **kw})


def auth_done(provider: str, **kw: Any) -> AuthEvent:
    return AuthEvent(event="done", data={"provider": provider, **kw})


def auth_error(provider: str, error: str, **kw: Any) -> AuthEvent:
    return AuthEvent(event="error", data={"provider": provider, "error": error, **kw})


def auth_cancelled(provider: str, **kw: Any) -> AuthEvent:
    return AuthEvent(event="cancelled", data={"provider": provider, **kw})


def credentials_not_supported(reason: str) -> dict[str, Any]:
    """Standard shape for ``set_credentials`` on kits that don't accept BYOK."""
    return {"ok": False, "error": reason}


__all__ = [
    "AuthEvent",
    "AuthStatus",
    "auth_cancelled",
    "auth_done",
    "auth_error",
    "auth_started",
    "auth_waiting",
    "credentials_not_supported",
]
