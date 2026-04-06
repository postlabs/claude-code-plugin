---
description: "Publish sprint actions to 2-tier folder structure"
argument-hint: "<output_dir> [actions_dir]"
user-invocable: true
allowed-tools:
  - Bash
  - Read
---

# Publish Actions

Run the publish script to convert sprint output into the 2-tier action folder structure.

## Input

- `output_dir`: Sprint output directory (e.g. `output/action_creator/naver`)
- `actions_dir` (optional): Target directory. Defaults to `actions` in the project root.

Parse from `$ARGUMENTS`. If no output_dir is provided, ask the user.

## Execution

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/publish.py <output_dir> <actions_dir>
```

Report the result to the user.
