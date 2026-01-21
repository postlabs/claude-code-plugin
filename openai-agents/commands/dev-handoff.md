---
description: Configure handoffs between agents for multi-agent workflows
argument-hint: [request]
allowed-tools: Read, Write, Edit, Grep, Glob
---

Configure agent handoffs: $ARGUMENTS

## Handoff Configuration

### Basic Handoff

```python
from agents import Agent

support = Agent(
    name="Support",
    instructions="Handle support requests",
    handoff_description="Transfer for customer support",
)

billing = Agent(
    name="Billing",
    instructions="Handle billing questions",
    handoff_description="Transfer for billing issues",
)

router = Agent(
    name="Router",
    instructions="Route users to appropriate department",
    handoffs=[support, billing],
)
```

### Customized Handoff

```python
from agents import Agent, handoff
from pydantic import BaseModel

class HandoffInput(BaseModel):
    reason: str
    priority: str

async def on_handoff(ctx, input_data: HandoffInput):
    log(f"Handoff: {input_data.reason}")

support_handoff = handoff(
    agent=support_agent,
    tool_name_override="transfer_to_support",
    tool_description_override="Transfer to support team",
    input_type=HandoffInput,
    on_handoff=on_handoff,
    is_enabled=lambda ctx, agent: ctx.context.user_tier == "premium",
)
```

### Input Filters

```python
from agents import handoff, HandoffInputData
from agents.extensions.handoff_filters import remove_all_tools

def custom_filter(data: HandoffInputData) -> HandoffInputData:
    # Remove sensitive data before handoff
    filtered = [m for m in data.history if not m.get("sensitive")]
    return HandoffInputData(history=filtered)

handoff_config = handoff(
    agent=target_agent,
    input_filter=custom_filter,  # or remove_all_tools
)
```

## Handoff Options

| Option | Type | Description |
|--------|------|-------------|
| `agent` | Agent | Target agent |
| `tool_name_override` | str | Custom tool name |
| `tool_description_override` | str | Custom description |
| `input_type` | BaseModel | Structured input |
| `on_handoff` | Callable | Callback on handoff |
| `input_filter` | Callable | Filter data |
| `is_enabled` | bool/Callable | Enable conditionally |

## Best Practices

1. **Clear Descriptions**: Each agent needs handoff_description
2. **Avoid Circular**: A → B → A creates infinite loops
3. **Filter Sensitive Data**: Use input_filter for privacy
4. **Conditional Handoffs**: Use is_enabled for feature flags
5. **Use Recommended Prompt**: Import from handoff_prompt extension

## Implementation

Configure the handoffs as requested.
Validate that no circular references exist.
