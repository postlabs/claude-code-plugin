---
description: "Publish sprint actions to web_dough profile directory"
argument-hint: "<output_dir> [--profile-dir <path>]"
user-invocable: true
allowed-tools:
  - Bash
  - Read
---

# Publish Actions

Run the publish script to save sprint output to `web_dough/<domain>/actions/`.

Actions are grouped by domain (extracted from each action's URL).

## Input

- `output_dir`: Sprint output directory (e.g. `output/action_creator/naver`)
- `--profile-dir` (optional): web_dough root. Auto-detects from Mojo profile if omitted.

Parse from `$ARGUMENTS`. If no output_dir is provided, ask the user.

## Execution

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/publish.py <output_dir>
```

Report the result to the user.
