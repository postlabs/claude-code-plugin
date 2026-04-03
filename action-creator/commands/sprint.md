---
description: "Run action creator sprint pipeline — discover website features and generate automation presets"
argument-hint: "<url>"
user-invocable: true
allowed-tools:
  - Agent
  - Read
  - Write
  - Bash
  - Glob
  - Grep
  - WebFetch
---

# Action Creator Sprint Pipeline

You are orchestrating a sprint-based action creation pipeline with 3 agents: **Planner**, **Generator**, **Evaluator**.

## Input

Target URL: `$ARGUMENTS`

If no URL is provided, ask the user for one.

## Working Directory Setup

Create a working directory for this run:

```
{project_root}/output/action_creator/{site_name}/
├── sprint_plan.yaml      ← Planner output
├── sprint_1/
│   ├── actions.yaml      ← Generator output
│   └── evaluation.yaml   ← Evaluator output
├── sprint_2/
│   └── ...
└── final/
    └── actions.yaml      ← Merged valid actions
```

Extract `site_name` from the URL (e.g., `https://www.naver.com` → `naver`).

## Pipeline

### Phase 0: Preparation

1. Create the output directory.
2. Note the site name and entry URL.

### Phase 1: Planner

Spawn the **action-creator:planner** agent:

```
Agent(subagent_type="action-creator:planner")
```

**Prompt the Planner with:**
- The target URL
- The site name
- Ask it to write `sprint_plan.yaml` in the working directory

**After Planner completes:**
1. Read `sprint_plan.yaml` from the Planner's working directory.
2. If `login_required: true` → report to user and stop.
3. If no sprints → report to user and stop.
4. Count total scenarios across all sprints. Report the plan to the user.

### Phase 2: Sprint Loop

For each sprint in the plan:

#### Step 2a: Generator

Spawn the **action-creator:generator** agent:

```
Agent(subagent_type="action-creator:generator")
```

**Prompt the Generator with:**
- The site name, entry URL
- The sprint's scenarios (names, flow descriptions, expected actions, inputs, outputs)
- The sprint's success criteria
- Instruct it to read `${CLAUDE_PLUGIN_ROOT}/prompts/schema.txt` for the actions.yaml format
- Instruct it to write `actions.yaml` in the sprint working directory

**If this is a RETRY** (Evaluator found failures):
- Include the Evaluator's feedback: which actions failed, error details, fix hints
- Include the previous actions.yaml content so Generator can fix specific actions
- Instruct Generator to preserve passing actions and only fix failed ones

#### Step 2b: Validate Generator Output

After Generator completes:
1. Read the generated `actions.yaml`.
2. Basic checks (is it valid YAML? does it have actions with steps?).
3. If empty or invalid → log error, skip to next sprint.

#### Step 2c: Evaluator

Spawn the **action-creator:evaluator** agent:

```
Agent(subagent_type="action-creator:evaluator")
```

**Prompt the Evaluator with:**
- The site name, entry URL
- The sprint's success criteria
- The content of `actions.yaml` to test
- Instruct it to write `evaluation.yaml` in the sprint working directory

#### Step 2d: Check Evaluation Results

After Evaluator completes:
1. Read `evaluation.yaml`.
2. Count PASS vs FAIL results.

**If ALL PASS:**
- Log success. Move to next sprint.

**If some FAIL:**
- Check: are the failures identical to the previous attempt?
  - **Yes (no progress):** Log the stuck failures. Move to next sprint with partial results.
  - **No (progress made):** Go back to Step 2a with Evaluator feedback (RETRY).

**Budget rule:** Maximum 3 attempts per sprint (1 initial + 2 retries). After 3 attempts, take whatever passed and move on.

### Phase 3: Merge & Report

After all sprints complete:

1. Read all `actions.yaml` files from each sprint directory.
2. Merge all valid actions into `final/actions.yaml`.
3. Report summary to user:

```
Site: {site_name}
Sprints: {passed}/{total} passed
Actions: {count} generated
Failed: {count} (details in sprint directories)
```

## Important Rules

- **Spawn agents sequentially** — Planner first, then Generator/Evaluator per sprint.
- **Each agent gets a fresh context** — pass all needed information in the prompt, don't assume agents share state.
- **File-based communication** — agents write YAML files, you read them and pass content to the next agent.
- **Report progress** — after each sprint, tell the user what happened.
- **Don't modify agent output** — you read and route, you don't edit actions.yaml or evaluation.yaml yourself.
- **Match site language** — if the site is Korean, scenario names and descriptions should be in Korean.
