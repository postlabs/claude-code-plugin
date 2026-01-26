---
name: sync
description: Check recent changes from other sessions and show git log
allowed-tools:
  - Bash
---

# Git Sync - Check Recent Changes

Check what other sessions have changed recently.

## Steps

1. Run `git fetch` to get latest remote changes
2. Run `git log --oneline -20 origin/main` to show recent commits
3. Summarize what changed and which areas were affected (based on AFFECTS tags)
4. If there are local uncommitted changes, mention them

## Output Format

Present a concise summary:
- Number of new commits since last check
- Key changes by scope (feat, fix, api, etc.)
- Areas affected (frontend/backend/both)
- Any potential conflicts with current work
