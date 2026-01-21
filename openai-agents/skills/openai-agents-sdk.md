# OpenAI Agent SDK Knowledge

This skill provides comprehensive knowledge about the OpenAI Agent SDK.

## Overview

The OpenAI Agents SDK is a framework for building multi-agent workflows with:
- **Agents**: LLMs with instructions and tools
- **Handoffs**: Agent-to-agent delegation
- **Guardrails**: Input/output validation
- **Sessions**: Memory and state persistence
- **Tracing**: Debugging and monitoring

## Core Concepts

### Agent Creation
```python
from agents import Agent, Runner

agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant",
    model="gpt-4o",
    tools=[...],
    handoffs=[...],
)

result = Runner.run_sync(agent, "Hello")
```

### Tools

#### Function Tools
```python
from agents import function_tool

@function_tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {city}: Sunny"
```

#### Hosted Tools
- WebSearchTool: Search the web
- FileSearchTool: Search vector stores
- CodeInterpreterTool: Execute code
- ImageGenerationTool: Generate images

### Handoffs
```python
from agents import handoff

agent = Agent(
    handoffs=[
        handoff(agent=other_agent, tool_description="Transfer to specialist")
    ]
)
```

### Guardrails
```python
from agents import input_guardrail, output_guardrail

@input_guardrail
async def validate_input(ctx, agent, input):
    return GuardrailFunctionOutput(tripwire_triggered=False)
```

### Sessions
```python
from agents.extensions.session import SQLiteSession

session = SQLiteSession(db_path="conversations.db")
```

### Tracing
```python
from agents import trace

with trace("My Workflow"):
    result = Runner.run_sync(agent, "Hello")
```

## Best Practices

1. Use clear, specific instructions
2. Create specialized agents for different tasks
3. Use handoffs for complex workflows
4. Add guardrails for safety
5. Enable tracing for debugging
