---
name: session-sync
description: >
  Write a session summary to docs_hj/ and commit+push all changes including the summary.
  Combines /session-summary and /git-sync into one step. Use at the end of any plan
  execution, refactor, debugging session, or multi-step task. Triggers: "session sync",
  "save and push", "wrap up session", "sync session", or /session-sync.
---

# Session Sync

Combines session summary + git commit + push in one shot.

## Procedure

### Step 1: Write Session Summary

Create `docs_hj/YYYY-MM-DD-<slug>.md` with the full session summary format (see below).
If a summary already exists for this session, update it rather than creating a new file.

```bash
mkdir -p docs_hj
```

**Filename:** `docs_hj/YYYY-MM-DD-<slug>.md` (kebab-case, specific enough to identify at a glance)

**Required sections:**
```markdown
# Session: <Title>

**Date:** YYYY-MM-DD
**Status:** completed | partial | blocked

## Objective
What was the goal? 1-3 sentences including the "why."

## Plan
The original plan or approach as understood at the start.

## What Was Done
Step-by-step account: files created/modified/deleted, commands run, key decisions.

## What Worked
Specific approaches, tools, patterns that succeeded.

## What Failed (and Why)
Every dead end: what was tried, the error/symptom, root cause, why the alternative was chosen.
Include actual error messages. This is the most important section.

## Gotchas & Landmines
Non-obvious discoveries: unexpected behaviors, version quirks, misleading docs, order dependencies.

## Open Issues / Next Steps
What's left? What should the next session pick up?

## Key Files
Most important files touched, with one-line notes.
```

### Step 2: Git Commit

Stage ALL changes including the docs_hj/ summary file.

```
[scope] short summary

- specific change 1
- specific change 2

AFFECTS: frontend|backend|both|none
```

**Scopes:** `feat`, `fix`, `refactor`, `api`, `schema`, `config`, `docs`

**IMPORTANT:** If there are already uncommitted code changes, commit them first with an appropriate
message, then commit the docs summary separately. Or combine into one commit if the summary
describes the same changes.

### Step 3: Push

```bash
git push
```

**CRITICAL:** Always push after committing. The whole point of this skill is to sync everything
to remote — code changes AND the session summary. Do not skip the push.

**IMPORTANT:** Always include the `docs_hj/` summary file in the push. This is the most commonly
skipped step. Verify with `git status` after push that working tree is clean.

## Guidelines

- Be brutally honest about failures in the summary
- Include actual error messages when pivotal
- Don't duplicate the git diff — focus on intent, reasoning, context
- One summary per session (don't append to old files)
- Always verify the docs file is included in the commit before pushing
