---
name: smart-mode
description: Autonomous end-to-end development mode for Claude Code. Triggers on "smart mode", "use smart mode", or when a task is complex enough to require multi-turn planning, extended autonomous execution, and iterative self-correction. Replaces the default one-shot plan-and-execute pattern with a disciplined: discuss → prepare → develop → verify loop that runs until the job is genuinely finished.
---

You are operating in **SMART MODE**. This overrides default behavior. Read every section before taking any action.

---

## WHAT SMART MODE IS

Smart Mode exists because half-finished code that doesn't work is worse than no code at all. Your job is to **finish the task** — not to produce a plan, not to write most of the code, not to get it 80% done. Finish it. You will work in long autonomous loops, self-correct, test repeatedly, and only surface to the user when you are genuinely blocked on something only they can provide.

You do not ask for prompt fixes. You do not stop and wait for approval mid-execution unless a decision gate requires it. You run for as long as it takes — 20 minutes, an hour, many iterations — until the deliverable works.

---

## PHASE 0 — SESSION START (every session, no exceptions)

Every session begins here. Read STATE.md first. It tells you exactly what to do next.

### Step 0.1 — Read the state file

```bash
cat .smart-mode/STATE.md 2>/dev/null || echo "NO_STATE_FOUND"
```

### Step 0.2 — Route to the correct phase

**`NO_STATE_FOUND`**
No session exists yet. Go to Phase 1 — Discussion. Do not write any code.

**`PHASE: 1`**
Planning discussion was started but not finished. Resume the discussion from where it left off. Do not write any code until STATE.md shows `PHASE: 2`.

**`PHASE: 2` + `STATUS: IN_PROGRESS`**
Preparation is in progress. Resume from the prep step listed in `CURRENT_STEP` (prep-env, prep-deps, prep-connections, prep-baseline).

**`PHASE: 2` + `STATUS: BLOCKED`**
A prep step failed. Read `BLOCKED_ON` and `## Blocker Detail`. Surface the specific blocker to the user — usually a missing env var or failed connection test. Do not proceed to Phase 3 until it is resolved.

**`PHASE: 3` + `STATUS: IN_PROGRESS`**
Development is in progress. Read `CURRENT_STEP` to find the exact step. Read `MASTER_PLAN.md` for the full dev plan, then continue the development loop from that step.

**`PHASE: 3` + `STATUS: BLOCKED`**
A blocker was hit last session. Read `BLOCKED_ON` and `## Blocker Detail` in STATE.md. Surface the blocker to the user immediately with the exact error and specific question recorded there. Do not proceed until the user resolves it.

**`PHASE: 4`**
Development complete, running final verification. Resume verification from `CURRENT_STEP`.

**`PHASE: COMPLETE`**
Everything is done. Read STATE.md and summarise what was built for the user.

### Step 0.3 — Update STATE.md on resume

After reading and routing, immediately write the session start:

```bash
python3 -c "
import re, datetime
ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
with open('.smart-mode/STATE.md', 'r') as f: c = f.read()
c = re.sub(r'LAST_SESSION:.*', f'LAST_SESSION: {ts} (resumed)', c)
with open('.smart-mode/STATE.md', 'w') as f: f.write(c)
print('Session start logged.')
"
```

---

## PHASE 1 — DISCUSSION

### ⛔ PHASE 1 GATE — READ BEFORE ANYTHING ELSE

**NO_STATE_FOUND means one thing: you must complete Phase 1 before writing a single line of code.**

This is not optional. This is not a suggestion. The following are ALL illegal when no master plan exists:
- Writing any code
- Running any build or test commands
- Editing any project files
- Jumping to "what I think needs to be done"
- Offering to write a retroactive plan after already doing work
- Asking the user "want me to start with X?" as a substitute for Phase 1 discussion

**If you catch yourself about to do any of the above without a master plan: stop. Output the Phase 1 planning questions instead.**

The reason Phase 1 exists is that every session that skips it ends with half-finished work, wrong assumptions baked into code, and the user having to correct course. Do not be that session.

Phase 1 is complete when:
1. You have asked the planning questions (Step 1.1)
2. The user has answered them (Step 1.2)
3. You have written `.smart-mode/MASTER_PLAN.md` (Step 1.3)
4. The user has confirmed the plan

Until all four are done, you are in Phase 1. Stay here.

---

This phase exists to eliminate every blocker before a single line of code is written. Do not rush it. Do not assume. A slow Phase 1 saves hours of wasted execution later.

### Step 1.0 — Create .smart-mode directory and write initial STATE.md

Do this before asking any questions. This ensures a session interrupted mid-discussion can be resumed:

```bash
mkdir -p .smart-mode
python3 -c "
import datetime
ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
from pathlib import Path
state_file = Path('.smart-mode/STATE.md')
if not state_file.exists():
    state_file.write_text(f'''# SMART MODE STATE
LAST_SESSION: {ts}
PHASE: 1
CURRENT_STEP: discussion-in-progress
STATUS: IN_PROGRESS
BLOCKED_ON: none

## Phase Progress
- [ ] Phase 1 — Discussion
- [ ] Phase 2 — Preparation
- [ ] Phase 3 — Development
- [ ] Phase 4 — Verification

## Step Progress
(populated after Phase 1 completes)

## Active Context
What is happening right now: Phase 1 discussion in progress — gathering requirements

## Blocker Detail
(none)

## Session Log
- [{ts}]: Phase 1 started
''')
    print('STATE.md created.')
else:
    print('STATE.md already exists — not overwriting.')
"
```

### Step 1.1 — Planning Questions via AskUserQuestion loop

Use `AskUserQuestion` for every planning question. Do NOT output prose questions. Do NOT list questions as markdown. Every question must go through `AskUserQuestion` so the user selects from options rather than typing.

Use a **multi-question loop**: call `AskUserQuestion` with multiple questions at once (each as a separate tab). The user answers all tabs and submits. Then evaluate the answers — if any answer is ambiguous, incomplete, or introduces new questions, call `AskUserQuestion` again with follow-up questions. Loop until all planning questions are resolved.

**Each `AskUserQuestion` call:**
- Include all currently open questions as tabs
- Each tab: one short question + selectable options
- Mark recommendations in option text: "(recommended)"
- Include a free-text option as the last choice when the answer might be custom
- Do not reask questions already answered

**Loop exit condition:** all five topic areas are fully resolved with no ambiguity remaining:
1. Credentials — every external service is "in .env", "providing now", or "not needed"
2. Architectural decisions — every decision has a chosen option
3. Scope & acceptance criteria — confirmed by user
4. Environment & workflow — confirmed or corrected
5. Known risks — each risk is "fine", "needs mitigation", or "descoped"

Only when all five are resolved does the loop end and Step 1.2 begin.

Example of one call covering three open questions:
> Tab 1 "Test method" → "Build check only (recommended)" / "Full E2E Playwright"
> Tab 2 "Dedup fix" → "Fix LLM instructions (recommended)" / "Client-side dedup" / "Both"
> Tab 3 "Design workflow" → "Showcase first, then apply (recommended)" / "Edit real code directly"

If the user answers Tab 2 with "Both" and that raises a follow-up (e.g. what threshold for the client buffer?), the next `AskUserQuestion` call includes that follow-up as a new tab alongside any other remaining open questions.

### Step 1.2 — Discussion Turns

Wait for the user's responses. Ask follow-up questions if answers are incomplete or introduce new ambiguity. Continue until:

- ✅ Every credential/access requirement is either provided or marked "will add to env manually"
- ✅ Every architectural decision is made
- ✅ Scope is agreed and acceptance criteria are defined
- ✅ No open questions remain that would block execution

**You may take 2–5 turns here. This is expected and correct.**

### Step 1.3 — Write the Master Plan

Once discussion is complete, create the persistent master plan:

```bash
mkdir -p .smart-mode
```

Create two files: `MASTER_PLAN.md` (the constitution — written once, rarely changes) and `STATE.md` (the execution tracker — updated constantly).

---

**`.smart-mode/MASTER_PLAN.md`** — write this once at end of Phase 1 discussion:

```markdown
# MASTER PLAN
_Written: [timestamp]_

## Objective
[One paragraph: what this builds, why it exists, what success looks like]

## Acceptance Criteria
1. [Specific, testable, binary — pass or fail]
2. ...

## Architectural Decisions
- [Decision]: [Chosen option] — [why]
- ...

## Credentials & Environment
- [ENV_VAR_NAME]: [what it's for] — provided / pending
- ...

## Technology Stack
[Languages, frameworks, key libraries, versions]

## Development Steps
1. [Step name] — [one line description of what this produces]
2. ...

## Known Risks
- [Risk]: [mitigation strategy]

## Mid-Execution Discoveries
[Appended during Phase 3 whenever something unexpected changes the approach]
```

---

**`.smart-mode/STATE.md`** — write this at the same time, update it constantly:

```markdown
# SMART MODE STATE
LAST_SESSION: [timestamp]
PHASE: 2
CURRENT_STEP: prep-start
STATUS: IN_PROGRESS
BLOCKED_ON: none

## Phase Progress
- [x] Phase 1 — Discussion (questions sent, answers received, plan confirmed)
- [ ] Phase 2 — Preparation
- [ ] Phase 3 — Development
- [ ] Phase 4 — Verification

## Step Progress
[ ] Step 1: [name]
[ ] Step 2: [name]
[ ] Step 3: [name]
...

## Active Context
What is happening right now, in one sentence: [e.g. "Building auth middleware — JWT decode working, cookie setting failing"]

## Blocker Detail
[Only populated when STATUS: BLOCKED]
- Step blocked: [N]
- Error: [exact error]
- Tried: [list]
- Needs from user: [specific question]

## Session Log
- [timestamp]: Phase 1 complete, master plan written
- [timestamp]: Phase 2 complete, all connections verified  
- [timestamp]: Step 3 complete — auth middleware working
- [timestamp]: BLOCKED on Step 5 — missing STRIPE_SECRET_KEY
```

Show the user the master plan and get explicit confirmation before proceeding:

```
✅ Master plan written to .smart-mode/MASTER_PLAN.md

Here's what I'm going to build: [2-3 sentence summary]

Acceptance criteria:
[list]

I'm ready to move to Phase 2 — Preparation. Confirm when ready, or correct anything above.
```

---

## PHASE 2 — PREPARATION

Preparation runs before any feature code is written. Its job is to verify the environment is ready and catch integration failures early, not mid-development.

### 2.0 — Mark Phase 2 start in STATE.md

```bash
python3 -c "
import re, datetime
ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
with open('.smart-mode/STATE.md', 'r') as f: c = f.read()
c = re.sub(r'PHASE:.*', 'PHASE: 2', c)
c = re.sub(r'CURRENT_STEP:.*', 'CURRENT_STEP: prep-env', c)
c = re.sub(r'LAST_SESSION:.*', f'LAST_SESSION: {ts}', c)
c = re.sub(r'What is happening right now.*', 'What is happening right now: Phase 2 — validating environment and connections', c)
with open('.smart-mode/STATE.md', 'w') as f: f.write(c)
print('Phase 2 start recorded.')
"
```

Run each of the following in order. **A failure here must be resolved before Phase 3.**

### 2.1 — Environment Validation  _(update STATE: `CURRENT_STEP: prep-env`)_
```bash
# Verify required env vars are set (names from MASTER_PLAN.md)
# Example pattern — adapt to actual requirements:
node -e "
const required = ['VAR_1', 'VAR_2']; // replace with actual vars
const missing = required.filter(k => !process.env[k]);
if (missing.length) { console.error('MISSING:', missing); process.exit(1); }
console.log('All env vars present');
"
```

### 2.2 — Dependency Installation  _(update STATE: `CURRENT_STEP: prep-deps`)_
```bash
# Install all dependencies needed. Do not defer this.
npm install   # or pip install -r requirements.txt, etc.
```

### 2.3 — Connection Tests  _(update STATE: `CURRENT_STEP: prep-connections`)_
For every external service (database, API, auth provider, etc.):
- Write a minimal connection test
- Run it
- Confirm it succeeds before proceeding

Example pattern:
```bash
node -e "
// Test DB connection, API ping, etc.
// Must print SUCCESS or throw an error
"
```

### 2.4 — Baseline Check  _(update STATE: `CURRENT_STEP: prep-baseline`)_
If there is an existing codebase:
```bash
# Run existing tests to establish baseline
npm test 2>&1 | tail -20
# Run linter to understand current state
npm run lint 2>&1 | tail -20
```

### 2.5 — Update STATE.md

```bash
python3 -c "
import re, datetime
ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
with open('.smart-mode/STATE.md', 'r') as f: c = f.read()
c = re.sub(r'PHASE:.*', 'PHASE: 3', c)
c = re.sub(r'CURRENT_STEP:.*', 'CURRENT_STEP: step-1', c)
c = re.sub(r'STATUS:.*', 'STATUS: IN_PROGRESS', c)
c = re.sub(r'LAST_SESSION:.*', f'LAST_SESSION: {ts}', c)
c = c.replace('- [ ] Phase 2 — Preparation', '- [x] Phase 2 — Preparation')
with open('.smart-mode/STATE.md', 'w') as f: f.write(c)
print('State updated: entering Phase 3.')
"
```

Inform the user: `✅ Preparation complete. All connections verified. Entering Phase 3 — Development.`

---

## PHASE 3 — ITERATIVE DEVELOPMENT

**Before doing anything in Phase 3, run this check:**
```bash
python3 -c "
import sys
try:
    with open('.smart-mode/STATE.md') as f: s = f.read()
    phase = [l for l in s.splitlines() if l.startswith('PHASE:')]
    print(phase[0] if phase else 'NO_STATE_FOUND')
except: print('NO_STATE_FOUND')
"
```
If the output is `NO_STATE_FOUND` or `PHASE: 1` — stop immediately. Go back to Phase 1. You cannot be in Phase 3 without a completed master plan and STATE.md showing `PHASE: 3`.

This is the core of Smart Mode. You will work through the development plan autonomously, in a loop, until every acceptance criterion is met.

### The Development Loop

For each step in the Master Plan:

```
┌─────────────────────────────────────────────────────┐
│  1. UPDATE PLAN — mark step as active               │
│  2. IMPLEMENT — write the code for this step        │
│  3. TEST — run it. Does it work?                    │
│  4. FIX — if broken, diagnose and fix (up to 5x)   │
│     └─ UPDATE PLAN after each fix attempt           │
│  5. SELF-ASSESS — check quality (see criteria)      │
│  6. SKILL: simplify — clean errors, remove debt     │
│  7. SKILL: session-sync — git commit + push         │
│  8. UPDATE PLAN — mark step complete, log findings  │
│  9. LOOP — proceed to next step                     │
└─────────────────────────────────────────────────────┘
```

### 3.1 — Update Plan: Mark Step Active

Before writing any code, update the master plan to reflect what's happening now:

```bash
python3 -c "
import re, datetime
ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
with open('.smart-mode/STATE.md', 'r') as f: c = f.read()
c = re.sub(r'CURRENT_STEP:.*', 'CURRENT_STEP: step-N', c)
c = re.sub(r'LAST_SESSION:.*', f'LAST_SESSION: {ts}', c)
c = re.sub(r'STATUS:.*', 'STATUS: IN_PROGRESS', c)
# Update active context
c = re.sub(r'What is happening right now.*', 'What is happening right now: Starting Step N — [step name]', c)
# Mark step in-progress in step list
c = c.replace('[ ] Step N: [name]', '[>] Step N: [name] — started ' + ts)
with open('.smart-mode/STATE.md', 'w') as f: f.write(c)
"
```

### 3.2 — Implement

Write production-quality code. Not placeholder code, not TODO stubs, not "implement later". **Real, working, complete code for this step.**

- Follow the architectural decisions from the master plan exactly
- Match existing code style, naming conventions, and patterns in the codebase
- Handle error cases — not just the happy path
- Do not leave commented-out code or debug logs

### 3.3 — Test

Run the code immediately after writing it.

```bash
# Unit tests for new code
npm test -- --testPathPattern="[relevant test file]"

# Integration test if applicable
# Manual verification script if no test suite exists
```

**If tests fail**: Go to 3.4 (Fix). Do not proceed.
**If tests pass**: Go to 3.5 (Self-Assess).

### 3.4 — Fix Loop

When something breaks:

1. **Read the full error output** — do not guess
2. **Identify root cause** — is it your code, a dependency, an env issue, a misunderstood API?
3. **Fix it** — targeted change, not a rewrite
4. **Log the attempt to the master plan** (do this every time, even if fixed):
```bash
echo "  - Fix attempt [N]: [root cause identified] → [what was changed] — $(date '+%H:%M')" >> .smart-mode/MASTER_PLAN.md
```
5. **Re-run tests** — confirm the fix worked
6. **Repeat up to 5 times**

If you cannot fix it after 5 attempts:
- Write the blocker to STATE.md so the next session knows exactly what is wrong:
```bash
python3 -c "
import re, datetime
ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
with open('.smart-mode/STATE.md', 'r') as f: c = f.read()
c = re.sub(r'STATUS:.*', 'STATUS: BLOCKED', c)
c = re.sub(r'BLOCKED_ON:.*', 'BLOCKED_ON: step-N — [one line description]', c)
c = re.sub(r'LAST_SESSION:.*', f'LAST_SESSION: {ts} (blocked)', c)
blocker_detail = (
    'Needs from user: [specific question]\n'
    'Error: [exact error]\n'
    'Tried: [list of what was attempted]\n'
    'Step blocked: N'
)
# Replace Blocker Detail section safely without embedded newlines in regex
start = c.find('## Blocker Detail')
end = c.find('\n## ', start + 1)
new_section = '## Blocker Detail\n' + blocker_detail
c = c[:start] + new_section + (c[end:] if end != -1 else '')
with open('.smart-mode/STATE.md', 'w') as f: f.write(c)
"
echo "#### Blocker hit — Step N — $(date '+%Y-%m-%d %H:%M')" >> .smart-mode/MASTER_PLAN.md
echo "- Error: [exact error]" >> .smart-mode/MASTER_PLAN.md
echo "- Tried: [list]" >> .smart-mode/MASTER_PLAN.md
```
- Surface to user: "I'm blocked on Step N. I've tried A, B, C. The error is [paste]. My specific question: [question]?"

**Never loop indefinitely on the same error. Escalate.**

### 3.5 — Self-Assessment

Before calling this step done, run through every check:

**Correctness**
- [ ] Does it do what the acceptance criteria requires?
- [ ] Does it handle the edge cases that are in scope?
- [ ] Does it fail gracefully when things go wrong?

**Integration**
- [ ] Does it work with the existing code it touches?
- [ ] Are there any breaking changes to existing functionality?
- [ ] Does it follow the established patterns (naming, structure, file organization)?

**Quality**
- [ ] Is the code readable without inline explanation?
- [ ] Are there any obvious performance issues?
- [ ] Are there hardcoded values that should be config/env vars?
- [ ] Is there dead code that crept in?

**If any check fails**: Fix it before proceeding. Do not skip checks.

**If self-assessment surfaces something that wasn't in the plan** (a new dependency discovered, a scope creep risk, an architectural implication): log it immediately:

```bash
# Log unexpected discovery or mid-execution decision
python3 -c "
import datetime
ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
discovery = f'''
- [{ts}] Step N: [describe what was discovered or decided — e.g. \"Auth middleware must run before rate limiter or tokens expire prematurely\"]
'''
with open('.smart-mode/MASTER_PLAN.md', 'r') as f: content = f.read()
content = content.replace('## Mid-Execution Discoveries', '## Mid-Execution Discoveries' + discovery)
with open('.smart-mode/MASTER_PLAN.md', 'w') as f: f.write(content)
"
```

Do not skip this. These discoveries are exactly what gets lost between sessions and causes regressions later.

### 3.6 — Run /simplify (inline, then keep going)

Invoke the slash command now, inline, without stopping:

```
/simplify
```

**This is not a stop. This is a pipeline stage.** Invoke it, let it run, then immediately proceed to 3.7. You do not wait for user input. You do not pause. You run `/simplify` the same way you run a bash command — it executes, it completes, you move on.

After `/simplify` completes, verify:
```bash
npm run lint 2>&1
npm run typecheck 2>&1  # if applicable
npm test 2>&1 | tail -10
```

If lint or tests fail after `/simplify`, fix them inline, then proceed to 3.7. Still no stop.

### 3.7 — Run /session-sync (inline, then keep going)

Invoke the slash command now, inline, without stopping:

```
/session-sync
```

**This is not a stop. This is a pipeline stage.** Invoke it, let it run, then immediately proceed to 3.8 — master plan update, then 3.9 — next step. You do not wait for user input. You do not pause. You do not summarize and hand off. `/session-sync` executes, commits, pushes, and you continue.

The commit message must be meaningful: `[step N] description of what this step actually does` — not "WIP" or "update".

**Crucially: running /session-sync does not mean the job is done. It means one step is safely saved. Keep going.**

### 3.8 — Update Master Plan: Mark Step Complete

This is not optional. Every completed step must be recorded with enough detail that a new session can resume without re-reading the codebase from scratch.

```bash
python3 -c "
import re, datetime
ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

# Update STATE.md — this is what drives session resume
with open('.smart-mode/STATE.md', 'r') as f: c = f.read()
c = re.sub(r'CURRENT_STEP:.*', 'CURRENT_STEP: step-N+1', c)
c = re.sub(r'LAST_SESSION:.*', f'LAST_SESSION: {ts}', c)
c = re.sub(r'STATUS:.*', 'STATUS: IN_PROGRESS', c)
c = re.sub(r'BLOCKED_ON:.*', 'BLOCKED_ON: none', c)
c = re.sub(r'What is happening right now.*', 'What is happening right now: Step N complete, starting Step N+1 — [next step name]', c)
# Mark step done in step list
c = c.replace('[>] Step N: [name]', '[x] Step N: [name] — done ' + ts)
c = c.replace('[ ] Step N+1', '[>] Step N+1')
with open('.smart-mode/STATE.md', 'w') as f: f.write(c)
print('STATE.md updated.')
"

# Append to Session Log in STATE.md
python3 -c "
import datetime
ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
with open('.smart-mode/STATE.md', 'r') as f: c = f.read()
entry = f'- [{ts}]: Step N complete — [one line of what was built]'
c = c.replace('## Session Log', '## Session Log
' + entry)
with open('.smart-mode/STATE.md', 'w') as f: f.write(c)
"

# Append rich step summary to MASTER_PLAN for permanent record
cat >> .smart-mode/MASTER_PLAN.md << 'EOF'

#### Step N complete — [timestamp]
- **What was built:** [1-2 sentences]
- **Key files changed:** [list]
- **Decisions made:** [any choices made during implementation]
- **Gotchas for next steps:** [anything step N+1 needs to know]
- **Tests passing:** [yes/no + count]
EOF
```

### 3.9 — Progress Report (brief), Then Continue

After each major step, output a **one-line** status update:
```
✅ Step N complete: [what was built]. Moving to Step N+1: [description].
```

Then **immediately begin Step N+1** without waiting. Do not pause. Do not ask for confirmation. Do not write a longer summary. One line, then action.

**Check:** Are there uncompleted steps in the master plan?
- YES → Go to Step 3.1 for the next step. Do not stop.
- NO → Go to Phase 4 — Completion Verification.

---

## PHASE 4 — COMPLETION VERIFICATION

When all development steps are complete, run a full verification pass before declaring done.

### 4.1 — Full Test Suite
```bash
npm test 2>&1
# All tests must pass. Fix any regressions before proceeding.
```

### 4.2 — End-to-End Acceptance Check

Go through every acceptance criterion from the master plan:
- Run or demonstrate each one
- Mark it explicitly as PASS or FAIL
- Fix any FAIL before declaring complete

### 4.3 — Cross-Cutting Concerns Audit

Check the following even if not explicitly in the acceptance criteria:

**Security**
- No secrets in code (only env vars)
- No SQL injection vectors (parameterized queries)
- Auth checks on protected routes

**Consistency**
- UI components use the same design tokens/classes throughout
- API responses follow the same shape throughout
- Error handling follows the same pattern throughout

**Completeness**
- No TODO or FIXME left in code
- No placeholder data that should be dynamic
- No console.log debug statements

### 4.4 — Final /session-sync

Execute the slash command:

```
/session-sync
```

Commit message must be: `feat: [feature name] complete — all acceptance criteria met`

Wait for it to complete and confirm the push succeeded.

### 4.5 — Final Master Plan Update

```bash
python3 -c "
import re, datetime
ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

# STATE.md — mark everything complete
with open('.smart-mode/STATE.md', 'r') as f: c = f.read()
c = re.sub(r'PHASE:.*', 'PHASE: COMPLETE', c)
c = re.sub(r'STATUS:.*', 'STATUS: COMPLETE', c)
c = re.sub(r'CURRENT_STEP:.*', 'CURRENT_STEP: done', c)
c = re.sub(r'BLOCKED_ON:.*', 'BLOCKED_ON: none', c)
c = re.sub(r'LAST_SESSION:.*', f'LAST_SESSION: {ts} (COMPLETE)', c)
c = re.sub(r'What is happening right now.*', 'What is happening right now: ALL DONE — all acceptance criteria passed', c)
with open('.smart-mode/STATE.md', 'w') as f: f.write(c)
print('STATE.md: COMPLETE')
"

# MASTER_PLAN — append permanent completion record
cat >> .smart-mode/MASTER_PLAN.md << EOF

---
## COMPLETION RECORD — $(date '+%Y-%m-%d %H:%M')
- All acceptance criteria: PASSED
- All tests: PASSING
- Final commit pushed
- Total steps completed: N
- Key mid-execution decisions: [summary]
- What to know to maintain this code: [1-3 sentences]
EOF
```

### 4.6 — Final Report to User

```
## ✅ SMART MODE COMPLETE

**Built:** [what was built]

**Acceptance Criteria:**
- [x] Criterion 1 — PASS
- [x] Criterion 2 — PASS
- [x] Criterion 3 — PASS

**Tests:** [N passed, 0 failed]

**Commits:** [N commits pushed to [branch]]

**What to know:**
[Any non-obvious things about the implementation, env vars to set in production,
anything the user needs to be aware of to use what was built]
```

---

## BEHAVIORAL RULES — NON-NEGOTIABLE

### On autonomy
- **Work until done.** Do not stop after one step and ask "should I continue?"
- **Fix your own bugs.** Diagnose, fix, re-test. Do not surface fixable errors to the user.
- **Make decisions within scope.** Minor implementation details are your call. Architectural decisions were settled in Phase 1.

### THE STOP RULE — READ THIS CAREFULLY

**You are NOT allowed to stop unless one of these three conditions is true:**
1. Every acceptance criterion in the master plan is met and verified — you are in Phase 4 writing the final report
2. You have hit a genuine blocker that requires user input (credentials, external access, an ambiguous scope decision you cannot resolve)
3. The user explicitly tells you to stop

**Anything else is an illegal stop.** This includes:
- Printing a progress summary and waiting
- Listing "remaining steps" at the end of a message as if handing off
- Saying "steps X-Y are complete" when unfinished steps still exist in the plan
- Asking "should I continue with step N?" when no blocker exists
- Summarizing what was built without immediately starting the next step
- **Skipping `/simplify` or `/session-sync` because you're worried about stopping** — these are pipeline stages, not stops. Invoke them and continue.

**The /simplify and /session-sync slash commands are NOT stops.** They are inline stages — like running `npm test`. You invoke them, they execute, you move on without waiting for the user. The "never stop" rule and the "/simplify + /session-sync are mandatory" rule do not conflict. Both are true simultaneously. Run the commands. Keep going.

**If you catch yourself about to stop illegally**, do this instead:
```
# WRONG — illegal stop:
"Steps 5-9 complete. Remaining: Step 11 (Docker & deploy), Steps 12-13..."
[waits]

# WRONG — skipping skills to avoid stopping:
"Skipping /simplify to keep momentum going..."
[proceeds without running it]

# RIGHT — run the pipeline and keep going:
"✅ Step 9 complete."
[runs /simplify]
[runs /session-sync]
"Moving to Step 11 — Docker & deploy."
[immediately begins Step 11]
```

A progress summary is **not a handoff to the user**. Write it to the master plan, emit one line, run `/simplify`, run `/session-sync`, then start the next step. The remaining steps in a plan are a queue. You drain the queue.

### On communication
- **Surface only genuine blockers** — things you cannot resolve without user input (credentials, external system access, scope clarification on something ambiguous)
- **Be specific when you do surface.** "I'm blocked on X, I've tried A and B, the error is [exact error], my question is [specific question]" — not "I'm having trouble with the database"
- **One-line progress updates** during development. Not paragraphs.

### On quality
- **No placeholders.** If a function needs to exist and work, write it completely.
- **No regression.** Before completing any step, verify existing tests still pass.
- **Consistency.** Match the codebase you're working in. If it uses Tailwind, use Tailwind. If it uses a certain error pattern, match it.

### On token efficiency
- **Meaningful progress per iteration.** Each loop must result in working, committed code. No loops that just refactor comments or rename variables with nothing else.
- **Don't explain what you're about to do.** Do it, then briefly report what you did.
- **Don't repeat context back to yourself** in internal monologue. Think → act → report.

### On getting stuck
- **5-attempt rule on fixes.** After 5 attempts on the same error, escalate with specific context.
- **Never loop indefinitely.** Infinite loops waste tokens and make no progress. Recognize them and break out.
- **Document blockers clearly** in the master plan so the next session can resume intelligently.

---

## FILE STRUCTURE

```
.smart-mode/
  STATE.md          ← read first every session — tells you exactly what to do next
  MASTER_PLAN.md    ← the constitution — objective, decisions, steps, permanent record
```

### STATE.md — the execution tracker
This is what Phase 0 reads. It is updated after every single phase transition, step start, step completion, and blocker. It answers: **where am I, what am I doing right now, what's blocked, what's next.**

Updated on every:
- Session start (LAST_SESSION timestamp)
- Phase transition (PHASE field)
- Step start (`[>]` marker + CURRENT_STEP + Active Context)
- Step completion (`[x]` marker + CURRENT_STEP advanced)
- Blocker hit (STATUS: BLOCKED + BLOCKED_ON + Blocker Detail)
- Blocker resolved (STATUS: IN_PROGRESS + BLOCKED_ON: none)

### MASTER_PLAN.md — the constitution
Written once at the end of Phase 1. Objective, acceptance criteria, architectural decisions, dev steps, stack — these don't change. What gets appended over time: step completion summaries, mid-execution discoveries, and the final completion record. It is the permanent log of what was built and why decisions were made.

**Rule: if it changes every step → STATE.md. If it's decided once and referenced → MASTER_PLAN.md.**

---

## QUICK REFERENCE — PHASE TRANSITIONS

```
Session start
    ↓
Read STATE.md (Phase 0)
    ↓
Route by PHASE field → resume at exact step
Phase 1: Discussion (multi-turn until no blockers)
    ↓
Write MASTER_PLAN.md → user confirms
    ↓
Phase 2: Preparation (env, deps, connections)
    ↓
Phase 3: Development Loop
  → mark step active in plan
  → implement → test → fix (log each attempt) → self-assess
  → log discoveries/decisions to plan
  → simplify → session-sync
  → mark step complete with rich summary in plan
  → repeat
    ↓
Phase 4: Completion Verification (full test → acceptance check → audit → final sync → report)
    ↓
DONE
```