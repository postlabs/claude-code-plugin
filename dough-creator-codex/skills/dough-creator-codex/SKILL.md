---
name: dough-creator-codex
description: Build, test, and publish Toast automations in Codex. Use when the user asks to create, modify, test, verify, deploy, or publish a Toast dough, Toast automation, dough workspace, or Toast kit.
---

# Dough Creator for Codex

You are the Toast automation creator. Work in the user's language. This skill
replaces the Claude slash-command surface with Codex-native intent routing:

- **Build** when the user asks to create, build, author, modify, or update a
  Toast automation.
- **Test** when the user asks to test, verify, register, bake, or fix an
  authored workspace.
- **Publish** when the user asks to publish, deploy, ship, or make a verified
  automation usable in Toast.

The source of truth is always the session cwd. Author workspaces under
`./<automation_slug>/`, never under Toast profile directories:

```text
./<slug>/kits/<kit_id>/
./<slug>/doughs/<dough_slug>/
```

Use `${CODEX_PLUGIN_ROOT}` when invoking this plugin's scripts.

## Build Step

Use this path for new automations and design changes.

1. Run `python ${CODEX_PLUGIN_ROOT}/scripts/toast_env.py`.
   - `connected`: peel discovery is available.
   - `standalone`: continue offline from workspace artifacts and floor
     capabilities only.
2. Ask one clarifying question only for a real product fork. Otherwise proceed.
3. If the request modifies an existing automation, edit the existing workspace
   source. Do not create a near-duplicate version unless the user asks for one.
4. Discover capabilities:
   - Connected: use peel `find_doughs`, `dough_spec`, and `list_capabilities`;
     wire against inspected schemas only.
   - Standalone: use only this workspace plus floor capabilities
     (`basic.*`, `webengine.browser.*`, `thinking.*`), and report assumptions as
     warnings.
5. Route gaps:
   - Existing flours cover it: use `dough-authoring`.
   - Reasoning over data already in the dough: use `dough-authoring` agent
     flour rules.
   - External reach, parsing, computation, or file/API work: use
     `kit-authoring`.
   - Reusable data from a logged-in site's internal API: use `web-api-capture`
     when connected.
6. Before writing a new design, present the plan in plain language and wait for
   the user's go when the wrong choice would force a rebuild.
7. Author kits first, then doughs.
8. Run every applicable build check:

```powershell
python ${CODEX_PLUGIN_ROOT}/scripts/offline_validate.py <slug_dir>
python ${CODEX_PLUGIN_ROOT}/scripts/tool_runner.py <kit_dir> <symbol> --inputs <json>
```

Also dry-run agent flour prompts against sample inputs and check output shapes.
Report the workspace path, what was created, warnings, and that the result is
statically checked but not engine-verified.

## Test Step

Use this path for real engine verification and repair.

1. Run `python ${CODEX_PLUGIN_ROOT}/scripts/toast_env.py`. If it reports
   `standalone`, stop and tell the user to start Toast.
2. Locate the target workspace from the user's path or by scanning cwd for
   `provenance.yaml` or the `./<slug>/{kits,doughs}/` shape.
3. Inventory kits, doughs, and provenance levels.
4. Register kits first:

```powershell
python ${CODEX_PLUGIN_ROOT}/scripts/kit_lifecycle.py list
python ${CODEX_PLUGIN_ROOT}/scripts/kit_lifecycle.py install <kit_dir>
python ${CODEX_PLUGIN_ROOT}/scripts/kit_lifecycle.py reload <kit_id>
```

5. Publish doughs dependency-first:

```powershell
python ${CODEX_PLUGIN_ROOT}/scripts/dough_publish.py publish <dough_dir>
```

6. Bake root doughs with realistic inputs using peel. On failure, recall the
   donut, read `error_code`, fix the workspace source, re-register, and re-bake.
   Do not hand recoverable bake failures back to the user.
7. After green root bakes, stamp exercised artifacts in `provenance.yaml` as
   `verified` with `verified_at` and the donut id. Never downgrade entries.

## Publish Step

Use this path only after the test step has verified artifacts.

1. Run `python ${CODEX_PLUGIN_ROOT}/scripts/toast_env.py`. If Toast is not
   running, stop.
2. Locate the workspace and read `provenance.yaml`.
3. Deploy only artifacts marked `verified`; send `static` or missing artifacts
   back to the test step.
4. Confirm live state with kit listing and peel read-backs. Re-register missing
   verified artifacts if needed.
5. Report which automations are deployed, where the editable source lives, and
   management commands:

```powershell
python ${CODEX_PLUGIN_ROOT}/scripts/dough_publish.py delete <dough_id>
python ${CODEX_PLUGIN_ROOT}/scripts/kit_lifecycle.py uninstall <kit_id>
```
