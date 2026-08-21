"""The ``path IS the id`` mapping, shared by every profile tree that uses it.

``{profile}/doughs/`` and ``{profile}/spreads/`` both address an artifact by a
dot-form id mirroring its directory 1:1 — a plain ``.`` ↔ ``/`` split and join,
at any depth. A type shape co-locates inside one of those trees (a ``type.yaml``
beside its owner) and is addressed by the same id math.

``host_segment`` is the other half: the one-way naming rule that turns a
hostname or an account into the single folder name it lives under
(``search.shopping.naver.com`` → ``naver_com/shopping/search``). It is applied
when a folder is CREATED, never during resolution — the folder name is a label,
not an encoding, so nothing has to read a hostname back out of an id. Keeping it
injective is still worth the two lines: ``naver-com.com`` and ``naver.com.com``
are different sites, and a rule that flattened both to ``naver_com_com`` would
silently file them together.
"""

from __future__ import annotations

import re

# ONE grammar for a path segment, because a segment is one thing wherever it
# appears: a kit id segment IS a directory name IS a dough id segment. They were
# two regexes — `[a-z0-9_]` in the kit validator, the same in the dough rules —
# and the day the author root became an account handle they disagreed, so a
# perfectly legal dough root (`test@test_com`) was an illegal kit id.
#
# `-` is legal in a hostname label (`t-mobile_co_uk`); `@` separates an account's
# local part from its domain (`test@test_com`). Both are safe on disk and
# unreserved in a URL path segment (RFC 3986 pchar).
SEGMENT_GRAMMAR = "[a-z0-9_@-]{1,50}"
_SEGMENT_RE = re.compile(rf"^{SEGMENT_GRAMMAR}$")


def is_valid_segment(seg: str) -> bool:
    """True if ``seg`` is a legal path/id segment."""
    return bool(_SEGMENT_RE.match(seg))


# The random suffix of a uid — ``do-`` dough · ``sp-`` spread · ``ki-`` kit · ``ja-``
# jar · ``ba-`` basket, + 32 hex. RESERVED as a shape: a path segment may never take
# it, so a uid ``<handle>.<prefix>-<hex>`` can never be confused with a real path
# ending in a same-shaped segment. The right-anchor a uid is parsed by, and the
# shape ``validate_dough_path`` refuses.
_UID_RE = re.compile(r"^(do|sp|ki|ja|ba)-[0-9a-f]{32}$")


def is_uid_shaped(seg: str) -> bool:
    """True if ``seg`` is a uid's random suffix (``do-``/``sp-``/``ki-``/``ja-``/
    ``ba-`` + 32 hex) — the shape a path segment is forbidden to take."""
    return bool(_UID_RE.match(seg))


# A uid — ``<handle>.<prefix>-<32hex>``. The handle is the owner root (write-once,
# so it never drifts); the suffix is the random part. Own uid and a reference to it
# are the SAME string. Parsed right-anchored on the fixed uid suffix, never by
# counting dots (a handle carries no ``.`` but an account local part can). Every
# artifact stores it whole.
_SCOPED_UID_RE = re.compile(r"^(?P<handle>[a-z0-9_@-]{1,50})\.(?P<uid>(do|sp|ki|ja|ba)-[0-9a-f]{32})$")


def is_scoped_uid(s: str) -> bool:
    """True if ``s`` is a stored uid — ``<handle>.<prefix>-<32hex>``."""
    return bool(_SCOPED_UID_RE.match(s))


def parse_scoped(s: str) -> tuple[str, str] | None:
    """``<handle>.<prefix>-<hex>`` → ``(handle, prefix-hex)``, or ``None``."""
    m = _SCOPED_UID_RE.match(s)
    return (m.group("handle"), m.group("uid")) if m else None



def host_segment(host: str) -> str:
    """A hostname or account as the single folder name it lives under.

    ``.`` becomes ``_``; a literal ``_`` doubles, so no two hosts collide.
    """
    return host.replace("_", "__").replace(".", "_")


# ── Handle codec ──────────────────────────────────────────────────────────
# A reversible, path-safe encoding of an identity string into ONE segment.
# Keep ``[a-z0-9@-]`` literal; every other UTF-8 byte becomes ``_hh`` (lowercase
# hex). ``_`` itself is not in the keep set, so it is always an escape introducer
# — which is what makes decoding, and therefore injectivity, unambiguous. Output
# is a subset of SEGMENT_GRAMMAR, carries no ``.`` (the path delimiter), and always
# ends up non-uid-shaped for a real account (it keeps the ``@``).
_HANDLE_KEEP = frozenset("abcdefghijklmnopqrstuvwxyz0123456789@-")
_HEX = frozenset("0123456789abcdef")


def encode_handle(s: str) -> str:
    """Reversible path-safe encoding: keep ``[a-z0-9@-]``, else ``_hh`` per byte."""
    out: list[str] = []
    for b in s.encode("utf-8"):
        c = chr(b)
        out.append(c if c in _HANDLE_KEEP else f"_{b:02x}")
    return "".join(out)


def decode_handle(h: str) -> str:
    """Inverse of ``encode_handle``. Raises ``ValueError`` on any non-canonical
    input (bad/partial escape, illegal literal, invalid UTF-8)."""
    raw = bytearray()
    i, n = 0, len(h)
    while i < n:
        c = h[i]
        if c == "_":
            hx = h[i + 1:i + 3]
            if len(hx) != 2 or hx[0] not in _HEX or hx[1] not in _HEX:
                raise ValueError(f"bad escape at {i}")
            raw.append(int(hx, 16))
            i += 3
        elif c in _HANDLE_KEEP:
            raw.append(ord(c))
            i += 1
        else:
            raise ValueError(f"illegal char {c!r} at {i}")
    return raw.decode("utf-8")  # raises UnicodeDecodeError on invalid UTF-8


def is_canonical_handle(h: str) -> bool:
    """A handle is canonical only when it round-trips: ``encode(decode(h)) == h``.
    This is stricter than "decodes cleanly" — it also rejects an escaped keep-set
    byte (``_61`` for ``a``), uppercase hex (``_2E``), and any other non-canonical
    spelling of the same identity."""
    try:
        return encode_handle(decode_handle(h)) == h
    except (ValueError, UnicodeDecodeError):
        return False


def id_from_path(rel_path: str) -> str:
    """A tree-relative path as its dot-form id."""
    return ".".join(s for s in rel_path.replace("\\", "/").split("/") if s)


def path_from_id(artifact_id: str) -> tuple[str, ...]:
    """A dot-form id as its path segments."""
    return tuple(artifact_id.split("."))


def handle_of(artifact_id: str) -> str:
    """The OWNER root of a dot-form id — ``postlab``, ``test@test_com``, ``local``.

    The first segment, because "the id is the path, and its ROOT is who owns
    it". Unlike the rest of the path this is not a label: ownership does not
    move, so it is the one part of a path id that is already permanent.
    """
    return artifact_id.split(".", 1)[0]
