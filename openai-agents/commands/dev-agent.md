---
description: Create or modify agents with proper configuration
argument-hint: [request]
allowed-tools: Read, Write, Edit, Grep, Glob
---

Create or modify an OpenAI Agent SDK agent: $ARGUMENTS

## Agent Configuration Reference

```python
from agents import Agent, ModelSettings

agent = Agent(
    # Required
    name="AgentName",
    instructions="Clear, specific system prompt",

    # Model settings
    model="gpt-4.1",  # or gpt-5.2, gpt-4.1-mini
    model_settings=ModelSettings(
        temperature=0.7,
        tool_choice="auto",
    ),

    # Capabilities
    tools=[...],           # Function tools
    mcp_servers=[...],     # MCP connections
    handoffs=[...],        # Other agents

    # Safety
    input_guardrails=[...],
    output_guardrails=[...],

    # Output
    output_type=PydanticModel,  # Structured output
    handoff_description="When to hand off to this agent",
)
```

## Best Practices

1. **Instructions**: Write specific, actionable system prompts
2. **Naming**: Use descriptive names (CustomerSupport, DataAnalyzer)
3. **Model**: Match model to task complexity
4. **Tools**: Only include necessary tools
5. **Guardrails**: Add for safety-critical applications

## Dynamic Instructions

For personalized behavior:

```python
def get_instructions(context, agent):
    return f"Help {context.context.user_name}..."

agent = Agent(
    name="PersonalAgent",
    instructions=get_instructions,
)
```

## Implementation

Create or modify the agent following these patterns.
Validate the implementation using the agent-validator agent.
