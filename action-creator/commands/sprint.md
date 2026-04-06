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

# Action Creator Pipeline

You are orchestrating an action creation pipeline with 3 agents: **Planner**, **Generator**, **Evaluator**.

## Input

Target URL: `$ARGUMENTS`

If no URL is provided, ask the user for one.

## Working Directory Setup

Create a working directory for this run:

```
{project_root}/output/action_creator/{site_name}/
├── plan.yaml                ← Planner output
├── actions/
│   ├── {action_name}.yaml   ← Generator output (per action)
│   └── ...
├── evals/
│   ├── {action_name}.yaml   ← Evaluator output (per action)
│   └── ...
├── retry_1/
│   ├── actions/             ← Retry Generator output
│   └── evals/               ← Retry Evaluator output
└── final/
    └── actions.yaml         ← Merged valid actions
```

Extract `site_name` from the URL (e.g., `https://www.naver.com` → `naver`).

## Pipeline

### Phase 0: Preparation

1. Create the output directory.
2. **Start Chrome for Planner:**
   ```bash
   start chrome --remote-debugging-port=9222 --user-data-dir="C:/tmp/chrome-cdp-0" --no-first-run
   ```
   Wait 3 seconds, then verify:
   ```bash
   curl -s http://127.0.0.1:9222/json/version
   ```
   If it fails, warn the user and stop.
3. **Connect Planner session:**
   ```bash
   playwright-cli -s=planner attach --cdp=http://127.0.0.1:9222
   ```
4. Note the site name and entry URL.

### Phase 1: Planner

Spawn the **action-creator:planner** agent:

```
Agent(subagent_type="action-creator:planner")
```

**Prompt the Planner with:**
- The target URL
- The site name
- **Session name: `planner`**
- Ask it to write `plan.yaml` in the working directory

**After Planner completes:**
1. Read `plan.yaml` from the working directory.
2. If `login_required: true` → report to user and stop.
3. If no actions → report to user and stop.
4. Parse the plan: `scenarios[]` with `actions[]` and optional `chain`.
5. Collect all action names into a flat list.
6. Close Planner Chrome:
   ```bash
   playwright-cli -s=planner close
   ```

### Phase 1.5: Scenario Review (User Confirmation)

Display the scenario list to the user in this format:

```
## 발견된 시나리오

| # | 시나리오 | Actions | Chain |
|---|---------|---------|-------|
| 1 | 오늘의 급등주 뉴스 찾기 | list_top_gainers → get_stock_news | ✓ |
| 2 | 환율 변환 | convert_currency | - |
| 3 | ... | ... | ... |

총 {N}개 시나리오, {M}개 action

진행할 시나리오 번호를 선택하세요 (예: 1,3 또는 all):
```

**Wait for user response.** Then:
- `all` → proceed with all scenarios
- `1,3` → keep only selected scenarios, remove the rest
- User may also give feedback like "2번은 빼고" → adjust accordingly

Update the action list to include only selected actions.

### Phase 2: Generator (all actions in parallel)

Let N = number of selected actions.

#### Step 2a: Launch N Chrome instances

```bash
for i in $(seq 0 $((N-1))); do
  start chrome --remote-debugging-port=$((9222+i)) --user-data-dir="C:/tmp/chrome-cdp-$i" --no-first-run
done
sleep 3
for i in $(seq 0 $((N-1))); do
  playwright-cli -s=gen_$i attach --cdp=http://127.0.0.1:$((9222+i))
done
```

#### Step 2b: Spawn all Generators in parallel

Spawn **all Generator agents in a single message**:

```
Agent(subagent_type="action-creator:generator", description="Generator: action_0")
Agent(subagent_type="action-creator:generator", description="Generator: action_1")
...
Agent(subagent_type="action-creator:generator", description="Generator: action_N-1")
```

**Prompt each Generator with:**
- The site name, entry URL
- **Session name: `gen_0`** (or `gen_1`, `gen_2`, ... matching the index)
- The **single action** definition from the plan (name, description, entry_url, type, params, output, discovered_elements, snapshot_excerpt)
- Instruct it to read `${CLAUDE_PLUGIN_ROOT}/prompts/schema.txt` for the actions.yaml format
- Instruct it to write to `{working_dir}/actions/{action_name}.yaml`

#### Step 2c: Validate Generator Output

After all Generators complete:
1. Close all Chrome instances:
   ```bash
   playwright-cli close-all
   ```
2. Read each `actions/{action_name}.yaml` file.
3. Basic checks (valid YAML? has steps?).
4. Log any missing or invalid actions.

### Phase 3: Evaluator (all actions in parallel)

#### Step 3a: Launch N Chrome instances

```bash
for i in $(seq 0 $((N-1))); do
  start chrome --remote-debugging-port=$((9222+i)) --user-data-dir="C:/tmp/chrome-cdp-eval-$i" --no-first-run
done
sleep 3
for i in $(seq 0 $((N-1))); do
  playwright-cli -s=eval_$i attach --cdp=http://127.0.0.1:$((9222+i))
done
```

#### Step 3b: Spawn all Evaluators in parallel

Spawn **all Evaluator agents in a single message**:

```
Agent(subagent_type="action-creator:evaluator", description="Evaluator: action_0")
Agent(subagent_type="action-creator:evaluator", description="Evaluator: action_1")
...
```

**Prompt each Evaluator with:**
- The site name, entry URL
- **Session name: `eval_0`** (or `eval_1`, `eval_2`, ...)
- The **single action** YAML content to test
- The **action definition from the plan** (params, expected output)
- Instruct it to write `{working_dir}/evals/{action_name}.yaml`

#### Step 3c: Check Results

After all Evaluators complete:
1. Close all Chrome instances:
   ```bash
   playwright-cli close-all
   ```
2. Read all `evals/{action_name}.yaml` files.
3. Count PASS vs FAIL.
4. Report progress to user.

### Phase 4: Retry (FAIL actions only, parallel)

If some actions FAIL:

1. Check: are the failures identical to the previous attempt?
   - **Yes (no progress):** Log the stuck failures. Move to Phase 5 with partial results.
   - **No (progress made):** Continue retry.

2. Let F = number of failed actions. Create `retry_1/` directory.

3. Launch F Chrome instances and spawn F Generators in parallel (same as Phase 2, but only for failed actions).
   - Include Evaluator feedback (error, fix_hint) in each Generator prompt.
   - Write to `retry_1/actions/{action_name}.yaml`.

4. After Generators complete, launch F Chrome instances and spawn F Evaluators in parallel (same as Phase 3).
   - Write to `retry_1/evals/{action_name}.yaml`.

5. Check results again. If still FAIL, repeat with `retry_2/`.

**Budget rule:** Maximum 3 attempts per action (1 initial + 2 retries). After 3 attempts, take whatever passed and move on.

### Phase 5: Merge & Report

1. Clean up:
   ```bash
   playwright-cli close-all
   ```
2. Collect all PASS actions from `actions/` and `retry_*/actions/` (latest passing version).
3. Merge into `final/actions.yaml`.
4. Report summary to user:

```
Site: {site_name}
Actions: {pass_count}/{total_count} passed
Failed: {fail_count} (details in evals/)
Retries: {retry_count}
```

## Important Rules

- **Planner runs alone** with one Chrome instance.
- **Generators run in parallel** — each gets its own Chrome + session + output file.
- **Evaluators run in parallel** — each gets its own Chrome + session + output file.
- **Each agent gets a fresh context** — pass all needed information in the prompt, including the session name.
- **File-based communication** — agents write YAML files, you read them and pass content to the next agent.
- **Report progress** — after each phase, tell the user what happened.
- **Don't modify agent output** — you read and route, you don't edit YAML yourself.
- **Match site language** — if the site is Korean, scenario names and descriptions should be in Korean.
- **Always close Chrome** — run `playwright-cli close-all` between phases and at the end.
