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

### Phase 2: Generator (3-step: snapshot → ref selection → hydration)

The Generator phase splits into 3 deterministic steps. The snapshot file is the
single source of truth shared between all steps — ref mismatch is structurally impossible.

```
Step 2a: CODE  → navigate + browser_snapshot(filename=...) → snapshot files saved
Step 2b: LLM   → read each snapshot file, pick ref IDs → write action YAML (target_ref)
Step 2c: CODE  → selector_hydrator.py --action X --snapshot Y → final YAML with selectors
```

Let N = number of selected actions.

#### Step 2a: Capture snapshots (CODE)

Launch ONE Chrome, navigate to each action's entry URL, and save a snapshot file.
Substitute test parameter values into the URL (extract examples from param descriptions).

```bash
start chrome --remote-debugging-port=9222 --user-data-dir="C:/tmp/chrome-cdp-0" --no-first-run
sleep 3
playwright-cli -s=gen attach --cdp=http://127.0.0.1:9222
```

For each action:
1. Navigate to the action's entry URL (with test params substituted)
   using the Playwright MCP `browser_navigate` tool
2. Wait for DOM stability using `browser_evaluate`:
   ```javascript
   await new Promise(resolve => {
     let prev = 0;
     const check = () => {
       const curr = document.querySelectorAll('*').length;
       if (curr === prev && curr > 50) resolve();
       else { prev = curr; setTimeout(check, 1000); }
     };
     check();
   });
   ```
   This polls DOM element count every 1s. When it stops changing, the page is
   fully rendered. Works for any page type — no fixed sleep, no page-specific threshold.
3. Save snapshot using `browser_snapshot(filename="{working_dir}/snapshots/{action_name}.yml")`

After all snapshots are captured, close Chrome:
```bash
playwright-cli -s=gen close
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'chrome.exe' -and $_.CommandLine -like '*chrome-cdp*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
```

Verify all snapshot files exist before proceeding.

#### Step 2b: Select refs and write action YAMLs (LLM — you)

For each action, read its snapshot file and the plan action definition.
Then write the action YAML with `target_ref` values (NOT hand-written selectors).

Read the schema format from `${CLAUDE_PLUGIN_ROOT}/prompts/schema.txt`.

You can process all actions **sequentially** (read snapshot → write YAML → next)
or spawn **parallel sub-agents** (each reads its own snapshot file — no browser needed).

**If using sub-agents:** Spawn all Generator agents in a single message:
```
Agent(subagent_type="action-creator:generator", description="Generator: action_0")
Agent(subagent_type="action-creator:generator", description="Generator: action_1")
...
```

**Prompt each Generator with:**
- The site name, entry URL
- The action definition from the plan
- The **snapshot file path** `{working_dir}/snapshots/{action_name}.yml`
  (instruct the agent to READ this file for element discovery — NO browser interaction needed)
- Instruct it to read `${CLAUDE_PLUGIN_ROOT}/prompts/schema.txt` for the actions.yaml format
- Instruct it to write to `{working_dir}/actions/{action_name}.yaml`
- **CRITICAL:** The agent must use `target_ref` with ref IDs from the snapshot file, NOT hand-written selectors
- **CRITICAL:** The agent must include a `verified_with` field in the action YAML with the actual test parameter values used during snapshot capture. The validator uses these values for URL substitution and replay testing. Example:
  ```yaml
  get_stock_price:
    params:
      stock_code:
        type: string
        required: true
    verified_with:
      stock_code: "A005930"
  ```

#### Step 2c: Hydrate selectors (CODE — deterministic)

Run `selector_hydrator.py` for each action. This script:
- Reads the action YAML (with `target_ref` values)
- Reads the **same snapshot file** used in step 2b
- Finds each ref in the parsed tree
- Generates multi-strategy selectors via `generate_selector_set()`
- Generates `target_hint` for fallback re-finding
- Parameterizes selectors (replaces test values with `$param_name`)
- Overwrites the action YAML with hydrated selectors

```bash
HYDRATOR="${CLAUDE_PLUGIN_ROOT}/scripts/selector_hydrator.py"

for action_name in ${action_names[@]}; do
  PYTHONIOENCODING=utf-8 python3 "$HYDRATOR" \
    --action "{working_dir}/actions/${action_name}.yaml" \
    --snapshot "{working_dir}/snapshots/${action_name}.yml"
done
```

After hydration, verify each action YAML has `selector` fields (not `target_ref`).

#### Step 2d: Validate Generator Output

1. Read each `actions/{action_name}.yaml` file.
2. Basic checks: valid YAML? has steps? has `selector` (not `target_ref`)?
3. Log any missing, invalid, or un-hydrated actions.

### Phase 3: Evaluation (Code Validation + LLM Semantic Review)

Evaluation has two sub-phases: code-based selector validation (deterministic) and LLM semantic review.

#### Step 3a: Code Validation (selector_validator.py)

Launch ONE Chrome instance for code validation:

```bash
start chrome --remote-debugging-port=9222 --user-data-dir="C:/tmp/chrome-cdp-eval" --no-first-run
sleep 3
curl -s http://127.0.0.1:9222/json/version
```

Run `selector_validator.py` for each action. This script:
- Connects to Chrome via CDP
- Takes a live snapshot at each step
- Tests **every selector strategy independently** using the actual code resolver (`resolve_selector_from_spec`)
- Compares ref IDs (extract_text) or match counts (extract_list) across strategies
- Runs `replay_action()` for a full execution test

```bash
for action_file in {working_dir}/actions/*.yaml; do
  PYTHONIOENCODING=utf-8 pip_python_or_system_python \
    ${CLAUDE_PLUGIN_ROOT}/scripts/selector_validator.py \
    --cdp-port 9222 \
    --action "$action_file" \
    --out-dir {working_dir}/code_evals/
done
```

> **Python requirement:** The script needs `pyyaml` and `openai-agents` packages.
> Use whichever Python has these installed (system or project embedded).

Close Chrome after all validations:
```bash
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'chrome.exe' -and $_.CommandLine -like '*chrome-cdp*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
```

Read each `code_evals/{action_name}.eval.yaml` and log the status (PASS/WARN/FAIL).

#### Step 3b: LLM Semantic Review (parallel, no browser needed)

Spawn **all Evaluator agents in a single message** (no browser session required):

```
Agent(subagent_type="action-creator:evaluator", description="Evaluator: action_0")
Agent(subagent_type="action-creator:evaluator", description="Evaluator: action_1")
...
```

**Prompt each Evaluator with:**
- The **action YAML content** from `actions/{action_name}.yaml`
- The **code validation result** from `code_evals/{action_name}.eval.yaml`
- The **action definition from the plan** (params, expected output)
- Instruct it to write `{working_dir}/evals/{action_name}.yaml`

#### Step 3c: Check Results

After all Evaluators complete:
1. Read all `evals/{action_name}.yaml` files.
2. An action is FAIL if **either** code validation or LLM review says FAIL.
3. Count PASS vs FAIL.
4. Report progress to user.

### Phase 4: Retry (FAIL actions only, parallel)

If some actions FAIL:

1. Check: are the failures identical to the previous attempt?
   - **Yes (no progress):** Log the stuck failures. Move to Phase 5 with partial results.
   - **No (progress made):** Continue retry.

2. Let F = number of failed actions. Create `retry_1/` directory.

3. Re-run Phase 2 (snapshot → ref selection → hydration) for failed actions only:
   - Step 2a: Re-capture snapshots for failed actions (fresh page state)
   - Step 2b: Re-select refs with Evaluator feedback (error, fix_hint) included in the prompt
   - Step 2c: Re-hydrate with `selector_hydrator.py`
   - Write to `retry_1/actions/{action_name}.yaml`

4. Re-run Phase 3 (code validation + LLM review) for retried actions.
   - Write to `retry_1/evals/{action_name}.yaml`.

5. Check results again. If still FAIL, repeat with `retry_2/`.

**Budget rule:** Maximum 3 attempts per action (1 initial + 2 retries). After 3 attempts, take whatever passed and move on.

### Phase 5: Merge & Report

1. Clean up:
   ```bash
   playwright-cli close-all
   powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'chrome.exe' -and $_.CommandLine -like '*chrome-cdp*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
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
