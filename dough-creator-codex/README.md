# dough-creator-codex

Codex plugin for building **Toast automations** from natural-language requests.
It migrates the original Claude Code `dough-creator` workflow into Codex skills:
build, test, and publish.

## Workflow

Ask Codex to use Dough Creator for one of these jobs:

| Step | Needs Toast? | Does |
|------|--------------|------|
| Build | no | Authors artifacts under `./<slug>/`, then static-validates and unit-runs them. |
| Test | yes | Registers artifacts into Toast, bake-verifies root doughs, and repairs failures in place. |
| Publish | yes | Ships only artifacts stamped `verified` by the test step. |

The editable workspace stays in the current working directory:

```text
./<slug>/
├── kits/<kit_id>/
└── doughs/<dough_slug>/
```

## Requirements

- Python on `PATH`, or set `TOAST_PYTHON`.
- Build step: `pydantic` and `ruamel.yaml`.
- Test/publish: the Toast app running on `127.0.0.1:18587`, plus `mcp`,
  `httpx`, and `httpx-sse` for the vendored peel MCP server.

Install common dependencies with:

```powershell
pip install pydantic ruamel.yaml mcp httpx httpx-sse
```

## Layout

```text
.codex-plugin/plugin.json      Codex plugin manifest
.mcp.json                      peel MCP server configuration
skills/dough-creator-codex/    top-level build/test/publish router
skills/kit-authoring/          Toast kit authoring rules
skills/dough-authoring/        Toast dough and agent-flour authoring rules
skills/web-api-capture/        internal web API capture workflow
scripts/                       validation, unit-run, lifecycle, publish helpers
vendor/peel/                   vendored peel MCP server
vendor/engine_core/            offline validator slice
vendor/core_stub/              offline kit-tool unit-run stubs
```
