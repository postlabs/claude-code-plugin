---
name: session-sync
description: Write session summary to docs_hj/ and commit+push all changes
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Glob
  - Grep
argument-hint: "[optional commit message or scope]"
---

# Session Sync — Activate

Write a session summary, commit all changes, and push to remote. Read the full SKILL.md in this plugin directory for the complete protocol, then follow it exactly.

## Activation

1. Read the SKILL.md file from this plugin directory for the full session-sync protocol
2. Follow Step 1 — Write Session Summary to docs_hj/
3. Follow Step 2 — Git Commit with structured message
4. Follow Step 3 — Push to remote

If the user provided a commit message or scope as an argument, use it for the commit.
