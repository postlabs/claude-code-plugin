---
name: OpenAI Agents SDK - Handoffs
description: This skill should be used when the user asks to "configure handoffs", "transfer between agents", "set up agent routing", "add handoff callback", "filter handoff data", "create multi-agent workflow", or needs guidance on handoff configuration, input filters, or agent delegation in OpenAI Agents SDK.
version: 1.0.0
---

# OpenAI Agents SDK - Handoffs

## Overview

Handoffs enable agents to delegate tasks to other specialized agents. This creates flexible multi-agent workflows where each agent handles its area of expertise.

> **Latest Documentation**: Query Context7 MCP with Library ID `/openai/openai-agents-python` for up-to-date API references.

## Basic Handoff

```python
from agents import Agent

support_agent = Agent(
    name="Support",
    instructions="Handle customer support inquiries",
    handoff_description="Transfer for support issues",
)

billing_agent = Agent(
    name="Billing",
    instructions="Handle billing questions",
    handoff_description="Transfer for billing issues",
)

router = Agent(
    name="Router",
    instructions="Route users to the appropriate department",
    handoffs=[support_agent, billing_agent],
)
```

## Customized Handoff

```python
from agents import Agent, handoff
from pydantic import BaseModel

class HandoffInput(BaseModel):
    reason: str
    priority: str

async def on_handoff_callback(ctx: RunContextWrapper, input_data: HandoffInput):
    print(f"Handoff reason: {input_data.reason}, Priority: {input_data.priority}")

support_handoff = handoff(
    agent=support_agent,
    tool_name_override="transfer_to_support_team",
    tool_description_override="Transfer to support for technical issues",
    input_type=HandoffInput,
    on_handoff=on_handoff_callback,
    is_enabled=lambda ctx, agent: ctx.context.user_tier == "premium",
)

router = Agent(
    name="Router",
    handoffs=[support_handoff, billing_agent],
)
```

## Input Filters

Control what data passes to the next agent:

```python
from agents import handoff, HandoffInputData
from agents.extensions.handoff_filters import remove_all_tools

def custom_filter(data: HandoffInputData) -> HandoffInputData:
    # Remove sensitive messages from history
    filtered_history = [
        item for item in data.history
        if not item.get("sensitive")
    ]
    return HandoffInputData(history=filtered_history)

handoff_config = handoff(
    agent=target_agent,
    input_filter=remove_all_tools,  # Built-in filter
    # or: input_filter=custom_filter,
)
```

## Recommended Prompt Pattern

Use handoff-optimized prompts:

```python
from agents import Agent
from agents.extensions.handoff_prompt import (
    RECOMMENDED_PROMPT_PREFIX,
    prompt_with_handoff_instructions,
)

# Method 1: Direct prefix
agent = Agent(
    name="Router",
    instructions=RECOMMENDED_PROMPT_PREFIX + "Your specific instructions...",
    handoffs=[...],
)

# Method 2: Helper function
agent = Agent(
    name="Router",
    instructions=prompt_with_handoff_instructions("Your specific instructions..."),
    handoffs=[...],
)
```

## Handoff Options

| Option | Type | Description |
|--------|------|-------------|
| `agent` | `Agent` | Target agent for handoff |
| `tool_name_override` | `str` | Custom tool name |
| `tool_description_override` | `str` | Custom description |
| `input_type` | `BaseModel` | Structured handoff input |
| `on_handoff` | `Callable` | Callback when handoff occurs |
| `input_filter` | `Callable` | Filter data before handoff |
| `is_enabled` | `bool \| Callable` | Conditionally enable handoff |

## Best Practices

1. **Clear Descriptions**: Each agent needs a clear `handoff_description`
2. **Single Responsibility**: Specialized agents for specific tasks
3. **Graceful Fallback**: Router should handle unmatched requests
4. **Data Privacy**: Use input filters to remove sensitive data
5. **Conditional Routing**: Use `is_enabled` for feature flags

## Additional Resources

For the latest API references and detailed documentation, query Context7 MCP with Library ID `/openai/openai-agents-python`.
