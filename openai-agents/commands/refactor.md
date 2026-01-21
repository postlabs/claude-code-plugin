---
name: openai-agents:refactor
description: Refactor agent code for better structure and maintainability
argument-hint: [request]
allowed-tools: Read, Write, Edit, Grep, Glob
---

Refactor OpenAI Agent SDK code: $ARGUMENTS

## Common Refactoring Tasks

### 1. Split Large Agents

**Before:**
```python
agent = Agent(
    name="DoEverything",
    instructions="Handle support, billing, technical, sales...",
    tools=[tool1, tool2, tool3, ...many tools...],
)
```

**After:**
```python
support = Agent(name="Support", instructions="Handle support", tools=[support_tools])
billing = Agent(name="Billing", instructions="Handle billing", tools=[billing_tools])
technical = Agent(name="Technical", instructions="Handle technical", tools=[tech_tools])

router = Agent(
    name="Router",
    instructions="Route to appropriate department",
    handoffs=[support, billing, technical],
)
```

### 2. Extract Reusable Tools

**Before:**
```python
# Same code in multiple agents
@function_tool
def get_user(user_id: str): ...

@function_tool
def get_user_again(user_id: str): ...  # Duplicate!
```

**After:**
```python
# tools/user_tools.py
@function_tool
def get_user(ctx: RunContextWrapper[MyContext]) -> str:
    """Fetch user data."""
    return fetch_user(ctx.context.user_id)

# agents use shared tools
from tools.user_tools import get_user
```

### 3. Improve Instructions

**Before:**
```python
instructions="Help users"  # Too vague
```

**After:**
```python
instructions="""
You are a customer support agent for TechCorp.

Your responsibilities:
1. Answer product questions
2. Resolve billing issues
3. Escalate technical problems

Guidelines:
- Be professional and friendly
- Ask clarifying questions when needed
- Never share internal policies
"""
```

### 4. Add Type Hints

**Before:**
```python
def process_order(order):
    return order["id"]
```

**After:**
```python
from typing import TypedDict

class Order(TypedDict):
    id: str
    amount: float
    status: str

def process_order(order: Order) -> str:
    return order["id"]
```

### 5. Organize Code Structure

**Before:**
```
project/
└── main.py  # Everything in one file
```

**After:**
```
project/
├── agents/
│   ├── __init__.py
│   ├── router.py
│   ├── support.py
│   └── billing.py
├── tools/
│   ├── __init__.py
│   ├── user_tools.py
│   └── order_tools.py
├── config/
│   └── settings.py
├── tests/
│   └── test_agents.py
└── main.py
```

## Refactoring Guidelines

1. **Single Responsibility**: One agent, one purpose
2. **DRY Principle**: Extract shared tools and utilities
3. **Clear Naming**: Descriptive agent and tool names
4. **Type Safety**: Add type hints everywhere
5. **Testability**: Structure for easy testing

## Implementation

Analyze the current code structure.
Apply refactoring patterns as needed.
Validate changes with agent-validator.
