---
name: git-sync
description: This skill provides git commit protocols for multi-session collaboration. Use when committing changes, starting a new session, or after pulling to ensure consistent structured commit messages across Claude sessions working on the same codebase.
---

# Git Sync Protocol

Follow these conventions when working with git in multi-session collaborative environments.

## Commit Message Format

Use this structure for all commits:

```
[scope] short summary

- specific change 1
- specific change 2

AFFECTS: frontend|backend|both|none
```

**Scopes:** `feat`, `fix`, `refactor`, `api`, `schema`, `config`

**Example:**
```
[api] add user profile endpoint

- GET /api/users/:id returns profile data
- added UserProfile type to shared types
- includes avatar URL and preferences

AFFECTS: frontend
```

## Session Start / After Pull

Check recent changes from other sessions:

```bash
git log --oneline -20 origin/main
```

For details on a specific commit:
```bash
git show <commit-hash> --stat
```

## Before Committing

1. Stage changes:
```bash
git add -A
```

2. Commit with structured message:
```bash
git commit -m "[scope] summary

- change 1
- change 2

AFFECTS: frontend|backend|both|none"
```

3. Push:
```bash
git push
```

## AFFECTS Tag Reference

- `frontend` - Changes affect frontend code/types
- `backend` - Changes affect backend code/types
- `both` - Changes affect both frontend and backend
- `none` - Internal changes with no cross-boundary impact
