"""Standalone stand-in for the kit-side ``_core`` helper library.

Standalone (no Toast backend) shim: lets kit Python written against the real
``_core`` import and run unmodified under ``scripts/tool_runner.py``.
Mirrors the REAL module surface (signatures and behavior) for the subset
kits actually touch at tool-run time::

    from _core.profile import profile_dir, credentials_dir
    from _core.tokens import read_tokens, write_tokens
    from _core.auth_events import AuthEvent, AuthStatus

NOT included (runtime/connect-flow machinery, skipped for unit runs):
oauth_base, mcp_base, token_store, credentials, manifest_lite,
brand. ``connect.py`` is the only kit module that needs those — tool
unit runs never import it.

Divergence from the real ``_core.profile``: when the kit host hasn't
called ``set_root()`` (i.e. always, standalone), ``profile_dir()`` falls
back to ``$TOAST_STORE_DIR`` (default ``./.toast_store``) instead of
raising RuntimeError.
"""
