# dough-creator

Claude Code plugin that builds **Toast automations** from natural-language
requests. It is the kit-builder role, automated: where the in-app OVEN agent
can only compose existing capabilities, this plugin can also create the
capabilities themselves — full kits with Python tools.

```
/create "when a new video drops on this channel, summarize it to Telegram"
```

## How it works

- **Toast is the runtime, the plugin is the builder.** Everything is
  validated, bound, and test-baked by the locally running Toast backend
  (port 18587). The plugin authors files and drives the backend's APIs.
- **cwd is the source of truth.** Each `/create` run authors everything
  under `./<automation_slug>/` in the session's working directory — the user
  can see, version, and edit what was created. Toast holds only the
  published runtime copies; the plugin never writes into Toast profile
  directories and never guesses profile paths.

  ```
  ./<slug>/
  ├── kits/<kit_id>/          ──kit_lifecycle.py install──▶  backend copies into its profile
  │                              edit loop: edit here → reload
  └── doughs/<dough_slug>/    ──dough_publish.py publish──▶  POST/PUT /doughs
                                 modify loop: pull → edit → publish
  ```

- **peel MCP** (vendored under `vendor/peel/`, talks HTTP to the backend) for
  discovery / validation / baking. Two API surfaces peel does not cover get
  script wrappers: the **kit lifecycle API** (install / hot-reload /
  uninstall, `scripts/kit_lifecycle.py`) for binding new Python kits without
  a backend restart, and the **dough CRUD API**
  (`scripts/dough_publish.py` — publish / pull / delete) for registering
  user doughs. Publishing IS validation: a 422 response body carries the
  `validation_errors` to fix before republishing.
- **Routing:** existing flours → composition · reasoning gap → user agent
  flour · reach gap → new kit · browser gap → action-creator plugin.

## Requirements

- Toast app installed and **running** (`/create` preflights this).
- A Python with `mcp`, `httpx`, `httpx-sse` for the peel server. Resolution
  order in `vendor/peel/run_peel.cmd`: `TOAST_PYTHON` env → Toast dev repo's
  embedded Python → `python` on PATH. `dough_publish.py` runs on the same
  interpreter (it needs `ruamel.yaml`, which the embedded Toast Python
  ships; on ImportError it prints what to install).

## Layout

```
commands/create.md            /create orchestration
skills/kit-authoring/         kit contract (tools.py rules, kit.yaml, lifecycle loop)
skills/dough-authoring/       dough/flour authoring (fetches Toast's live build guide)
scripts/toast_env.py          preflight: backend health (+ profile listing as diagnostics)
scripts/kit_lifecycle.py      /kits install · reload · uninstall · list wrapper
scripts/dough_publish.py      user-dough publish · pull · delete (API-only)
vendor/peel/                  vendored peel MCP server (stdio, stdlib of the Toast repo)
```

## v1 scope

- Auth-less kits only (`auth: type: none`) — pure compute, public APIs, local
  files. OAuth kits (connect flows, console app registration) are out.
- Kits land as third-party kits in the local profile (copied there by the
  install API); the cwd source stays the permanent home. Promotion to
  official bundled kits (Toast repo, hashes, review) is a separate manual
  step.
- Web/browser automations are delegated to the action-creator plugin.
