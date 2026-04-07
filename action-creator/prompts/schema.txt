## actions.yaml Schema

Each action is a top-level key in actions.yaml. The key is the action name (snake_case).

### Action Definition

```yaml
action_name:
  description: "Human-readable description of what this action does"
  url: "https://example.com/page"        # Optional: target URL
  auto_generated: true                    # Always true for Action Creator
  created_at: "2026-04-02T12:00:00Z"     # ISO8601 timestamp
  params:                                 # Optional: input parameters
    param_name:
      type: string                        # string | number | boolean | integer
      required: true                      # true | false
      default: null                       # Optional default value
      description: "What this param is"   # Optional description
  steps:                                  # List of execution steps
    - action: click
      selector: ...
    - action: fill
      selector: ...
      value: $param_name                  # $-prefixed = parameter reference
  output:                                 # Optional: what this action produces
    type: list                            # text | list | table
    fields: [field1, field2]              # Field names in the output
  verified_with:                          # REQUIRED: actual test values used during snapshot
    param_name: "actual_value"            # The validator substitutes these into URLs and selectors
```

### Output Field

Actions that produce data (extract_text, extract_list) SHOULD define an `output` field so other actions can reference them:

- `text` — single value (e.g., a price, a name)
- `list` — repeating items (e.g., stock list, news list)
- `table` — structured rows with named columns

```yaml
# Example: action that produces a list
list_top_gainers:
  description: "급등주 상위 종목 목록 추출"
  output:
    type: list
    fields: [stock_name, price, change_rate]
  steps:
    - action: extract_list
      # ...

# Example: action that consumes output via param
get_stock_news:
  description: "특정 종목의 뉴스 목록 추출"
  params:
    stock_name:
      type: string
      required: true
  output:
    type: list
    fields: [title, date, source]
  steps:
    - action: fill
      value: $stock_name
      # ...
```

### Step Types

Each step has an `action` field and type-specific fields:

#### click — Click an element
```yaml
- action: click
  target_ref: e50                         # ref of the button from snapshot
```

#### fill — Type text into an input
```yaml
- action: fill
  target_ref: e42                         # ref of the textbox from snapshot
  value: $query                           # $param_name or {{ faker.email }} etc.
```

**IMPORTANT RULE for `fill`:** 
If you are filling a form field that requires unique data every time (like an email, ID, username, password, or current date), DO NOT hardcode literal values like `test_123@gmail.com`. You MUST use template variables instead:
- `{{ faker.email }}` - Generates a random email
- `{{ faker.user_name }}` - Generates a random username
- `{{ faker.name }}` - Generates a random name
- `{{ faker.password }}` - Generates a random password
- `{{ faker.phone_number }}` - Generates a random phone number
- `{{ date.today }}` - Inserts today's date

#### select — Select a dropdown option
```yaml
- action: select
  target_ref: e100                        # ref of the combobox from snapshot
  value: $category
```

#### press — Press a keyboard key
```yaml
- action: press
  key: Enter
```

#### navigate — Go to a URL
```yaml
- action: navigate
  url: "https://example.com/page"
```

#### scroll — Scroll the page
```yaml
- action: scroll
  direction: down                         # up | down | left | right
  distance: 500                           # pixels (optional)
```

#### extract_text — Extract text from an element
```yaml
- action: extract_text
  target_ref: e154                        # ref of the element to extract text from
```

#### extract_list — Extract repeating items
```yaml
- action: extract_list
  target_ref: e801                        # ref of the CONTAINER (list, table, etc.)
  limit: 20                               # Optional: max items
```

#### wait — Wait for an element to appear or a condition to be met
```yaml
- action: wait
  target_ref: e747                        # ref of the element to wait for
  timeout: 5000                           # Max wait in ms (default: 5000)
  state: visible                          # visible | hidden | attached (default: visible)
```

#### handle_dialog — Accept or dismiss browser dialogs (alert/confirm/prompt)
```yaml
- action: handle_dialog
  accept: true                            # true = OK/accept, false = Cancel/dismiss
  prompt_text: null                        # Optional: text to enter for prompt dialogs
```

#### select_custom — Select from non-standard dropdown (click trigger → click option)
Many sites use custom dropdowns (`<div>` + `<a>` lists) instead of native `<select>`.
This step opens the trigger element, then clicks the matching option by text.
```yaml
- action: select_custom
  trigger:
    target_ref: e200                      # ref of the trigger element
  option_text: $gender                    # Text of the option to select ($param or literal)
```

#### evaluate — Execute JavaScript for custom widget interactions
Use ONLY when standard actions (click, fill, select, select_custom) cannot target the element.
Common cases: custom scroll wheels, canvas-based UIs, programmatic state changes.
```yaml
- action: evaluate
  script: |
    const container = document.querySelector('.date_picker .lst_item._ul');
    const links = container.querySelectorAll('a.link');
    for (const l of links) {
      if (l.textContent.trim() === '$year') { l.click(); break; }
    }
  description: "Select year in custom scroll wheel date picker"
  params_used: [year]                     # List of $params referenced in script
```

**`evaluate` rules:**
- Always provide a `description` explaining what the script does
- Always list `params_used` for any $param references in the script
- Use `document.querySelector` with specific class/attribute selectors, not fragile indexes
- Keep scripts minimal — one DOM operation per evaluate step
- Prefer standard actions (click, fill, select_custom) over evaluate when possible

### Selector Format (target_ref)

**You do NOT write selectors by hand.** Instead, specify `target_ref` — the `ref` attribute
of the target element from the page snapshot. A post-processing step will automatically
generate multi-strategy selectors using `generate_selector_set()`.

```yaml
# For every step that targets an element, use target_ref:
- action: click
  target_ref: e43              # ref from snapshot: button "검색"

- action: fill
  target_ref: e42              # ref from snapshot: textbox "검색"
  value: $query

- action: extract_list
  target_ref: e801             # ref from snapshot: list (상품 목록 container)
  limit: 36

- action: extract_text
  target_ref: e154             # ref from snapshot: heading "상품명"

- action: wait
  target_ref: e747             # ref from snapshot: heading "검색결과"
  timeout: 5000
```

**Rules for choosing target_ref:**
1. Find the target element in the snapshot by its role, name, and position
2. Use the `ref=XXXX` attribute from the snapshot as target_ref value
3. For `extract_list`, prefer the **container** (e.g., `list`, `table`) over individual items (`listitem`, `row`) — containers produce better selectors
4. For `click`, `fill`, `select` — target the interactive element directly
5. For `wait` — target the element whose appearance confirms page readiness

**Steps that do NOT use target_ref** (no element targeting):
- `navigate` — uses `url` field
- `press` — uses `key` field
- `scroll` — uses `direction` / `distance` fields
- `handle_dialog` — uses `accept` field
- `evaluate` — uses `script` field

### Parameter References & Abstraction (CRITICAL)

**IMPORTANT RULE for Abstraction:**
If a specific keyword, entity name, or selection dictates the flow of your scenario (e.g., a "search query" that you type, which then appears in the URL, and later used to find the matching result link), **YOU MUST NEVER HARDCODE IT.**
You must formalize it as a parameter in the `params` block, and use `$param_name` or `{{param_name}}` consistently across all steps.

This applies to:
- `fill` values (e.g., typing the search query)
- `navigate` URLs (e.g., `https://shop.com/search?q={{query}}`)
- `selector` values (e.g., `value: 'link:"{{query}} 세부정보"'`)

Use `$param_name` or `{{param_name}}` in step values to reference action parameters:

```yaml
search_products:
  description: "Search for products"
  params:
    query:
      type: string
      required: true
      description: "Search keyword"
  steps:
    - action: fill
      selector:
        selectors:
          - strategy: role_name
            value: 'textbox:"Search"'
            priority: 0
      value: $query                       # References params.query
    - action: click
      selector:
        selectors:
          - strategy: role_name
            value: 'button:"Search"'
            priority: 0
```

### Action Naming Conventions

- `list_{page}` — Extract repeating items (e.g., `list_inbox`, `list_products`)
- `search_{page}` — Fill search + extract results (e.g., `search_inbox`)
- `submit_{page}` — Fill form + submit (e.g., `submit_compose`, `submit_login`)
- `get_{page}` — Extract detail info (e.g., `get_email_detail`)
- `navigate_{page}` — Navigate to a specific page/state
- `click_{element}` — Simple click action (e.g., `click_compose_button`)

### Complete Example

```yaml
search_inbox:
  description: "Search emails by keyword"
  auto_generated: true
  created_at: "2026-04-02T12:00:00Z"
  params:
    query:
      type: string
      required: true
      description: "Search keyword"
  steps:
    - action: fill
      target_ref: e42              # textbox "Search mail"
      value: $query
    - action: press
      key: Enter
    - action: extract_list
      target_ref: e200             # list "Messages" (container, not listitem)
      limit: 20

list_inbox:
  description: "List all emails in inbox"
  auto_generated: true
  created_at: "2026-04-02T12:00:00Z"
  steps:
    - action: extract_list
      target_ref: e200             # list "Messages" (container)
      limit: 50

submit_compose:
  description: "Compose and send a new email"
  auto_generated: true
  created_at: "2026-04-02T12:00:00Z"
  params:
    to:
      type: string
      required: true
      description: "Recipient email address"
    subject:
      type: string
      required: true
      description: "Email subject"
    body:
      type: string
      required: true
      description: "Email body"
  steps:
    - action: click
      target_ref: e10              # button "Compose"
    - action: fill
      target_ref: e55              # combobox "To"
      value: $to
    - action: fill
      target_ref: e60              # textbox "Subject"
      value: $subject
    - action: fill
      target_ref: e65              # textbox "Message Body"
      value: $body
    - action: click
      target_ref: e70              # button "Send"
```

### Inline Service Example (Custom Widget)

```yaml
check_fortune:
  description: "네이버 오늘의 운세 확인 (성별, 생년월일 입력 → 운세 결과)"
  url: "https://search.naver.com/search.naver?query=오늘의+운세"
  auto_generated: true
  created_at: "2026-04-03T00:55:00Z"
  params:
    gender:
      type: string
      required: true
      default: "남성"
      description: "성별 (남성/여성)"
    year:
      type: string
      required: true
      description: "출생 년도 (e.g., 1990)"
    month:
      type: string
      required: true
      description: "출생 월 (e.g., 3)"
    day:
      type: string
      required: true
      default: "1"
      description: "출생 일 (e.g., 15)"
  steps:
    - action: navigate
      url: "https://search.naver.com/search.naver?query=오늘의+운세"
    - action: select_custom
      trigger:
        target_ref: e300           # link "성별"
      option_text: $gender
    - action: click
      target_ref: e310             # link "생년월일"
    # Custom scroll wheel — evaluate는 target_ref 대신 script 사용
    - action: evaluate
      script: |
        const dp = document.querySelector('.pop_select_box._dateCustomSelect');
        const uls = dp.querySelectorAll('.lst_item._ul');
        const yearLinks = uls[0].querySelectorAll('a.link');
        for (const l of yearLinks) {
          if (l.textContent.trim() === '$year') { l.click(); break; }
        }
      description: "Select year in date picker scroll wheel"
      params_used: [year]
    - action: evaluate
      script: |
        const dp = document.querySelector('.pop_select_box._dateCustomSelect');
        const uls = dp.querySelectorAll('.lst_item._ul');
        const monthLinks = uls[1].querySelectorAll('a.link');
        for (const l of monthLinks) {
          if (l.textContent.trim() === '$month') { l.click(); break; }
        }
      description: "Select month in date picker scroll wheel"
      params_used: [month]
    - action: evaluate
      script: |
        const dp = document.querySelector('.pop_select_box._dateCustomSelect');
        const uls = dp.querySelectorAll('.lst_item._ul');
        const dayLinks = uls[2].querySelectorAll('a.link');
        for (const l of dayLinks) {
          if (l.textContent.trim() === '$day') { l.click(); break; }
        }
      description: "Select day in date picker scroll wheel"
      params_used: [day]
    - action: click
      target_ref: e350             # button "운세 확인하기"
    - action: handle_dialog
      accept: true
    - action: wait
      target_ref: e400             # heading "운세의 총운은"
      timeout: 5000
    - action: extract_text
      target_ref: e410             # paragraph (운세 결과 텍스트)
```

### site.yaml Schema

```yaml
site: site_name
entry_url: "https://example.com"
pages:
  page_name:
    url_pattern: "/path"
    verified: false
    discovered_at: "2026-04-02T12:00:00Z"
    discovered_via:
      trigger: null                       # or { click: element_name }
```

### pages/{page_name}.yaml Schema

```yaml
page: page_name
url_pattern: "/path"
elements:
  element_key:
    role: "button"
    name: "Submit"
repeating:
  group_key:
    role: "listitem"
    name: "Email row"
    fields:
      field1: "sender"
      field2: "subject"
```
