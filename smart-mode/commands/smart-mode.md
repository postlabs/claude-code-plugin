---
name: smart-mode
description: Activate autonomous end-to-end development mode (discuss → prepare → develop → verify)
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Glob
  - Grep
  - Agent
  - Skill
  - AskUserQuestion
argument-hint: "[optional task description]"
---

# Smart Mode — Activate

Activate Smart Mode for autonomous end-to-end development. Read the full SKILL.md in this plugin for the complete protocol, then follow it exactly.

## Activation

1. Read the SKILL.md file from this plugin directory for the full Smart Mode protocol
2. Follow Phase 0 — Session Start (read STATE.md or create new session)
3. Proceed through all phases autonomously until done

If the user provided a task description as an argument, use it as the initial task context for Phase 1 discussion.
