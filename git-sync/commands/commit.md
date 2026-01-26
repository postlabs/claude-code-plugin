---
name: commit
description: Create a structured commit following the git-sync protocol
allowed-tools:
  - Bash
  - Read
argument-hint: "[optional message or scope]"
---

# Git Sync - Create Commit

Create a commit following the git-sync protocol format.

## Steps

1. Run `git status` to see current changes
2. Run `git diff --stat` to understand what files changed
3. Determine appropriate scope: `feat`, `fix`, `refactor`, `api`, `schema`, `config`
4. Determine AFFECTS tag: `frontend`, `backend`, `both`, `none`
5. Stage changes with `git add -A` (or specific files if requested)
6. Create commit with structured message format:

```
[scope] short summary

- specific change 1
- specific change 2

AFFECTS: frontend|backend|both|none

Co-Authored-By: Claude <noreply@anthropic.com>
```

7. Ask user if they want to push

## If User Provides Arguments

- If scope provided (e.g., "fix"), use that scope
- If message provided, incorporate into summary
