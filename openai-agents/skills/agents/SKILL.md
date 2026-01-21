---
name: OpenAI Agents SDK - Agent Creation
description: This skill should be used when the user asks to "create an agent", "define agent instructions", "configure agent model", "set up dynamic instructions", "use structured output", "clone an agent", or needs guidance on Agent class parameters, model settings, or agent behavior configuration in OpenAI Agents SDK.
version: 1.0.0
---

# OpenAI Agents SDK - Agent Creation

## Overview

Agents are the core building blocks of OpenAI Agents SDK. Each agent wraps an LLM with instructions, tools, handoffs, and guardrails. This skill covers agent creation, configuration, and best practices.

> **Latest Documentation**: Query Context7 MCP with Library ID `/openai/openai-agents-python` for up-to-date API references.

## Core Concepts

### Basic Agent Creation

```python
from agents import Agent, Runner

agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant",
    model="gpt-4.1",  # Default model
)

# Synchronous execution
result = Runner.run_sync(agent, "Hello!")
print(result.final_output)

# Asynchronous execution
result = await Runner.run(agent, "Hello!")
```

### Agent Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Agent identifier (required) |
| `instructions` | `str \| Callable` | System prompt. Can be dynamic function: `(context, agent) -> str` |
| `model` | `str` | LLM model to use |
| `model_settings` | `ModelSettings` | temperature, top_p, tool_choice, etc. |
| `tools` | `list[Tool]` | Available tools |
| `mcp_servers` | `list[MCPServer]` | MCP server connections |
| `handoffs` | `list[Agent \| Handoff]` | Agents to delegate to |
| `input_guardrails` | `list[InputGuardrail]` | Input validation |
| `output_guardrails` | `list[OutputGuardrail]` | Output validation |
| `output_type` | `type` | Structured output type (Pydantic, dataclass) |
| `handoff_description` | `str` | Description shown during handoff |
| `reset_tool_choice` | `bool` | Reset tool_choice after tool use (default: True) |

### Dynamic Instructions

Create context-aware instructions using a function:

```python
from agents import Agent, RunContextWrapper

def get_instructions(context: RunContextWrapper, agent: Agent) -> str:
    user_name = context.context.user_name
    return f"You are helping {user_name}. Be friendly and helpful."

agent = Agent(
    name="PersonalAssistant",
    instructions=get_instructions,
)
```

### Model Settings

Configure model behavior:

```python
from agents import Agent, ModelSettings

agent = Agent(
    name="Assistant",
    model="gpt-5.2",
    model_settings=ModelSettings(
        temperature=0.7,
        top_p=0.9,
        tool_choice="auto",  # "auto" | "required" | "none" | specific_tool
        reasoning={"effort": "medium"},  # GPT-5.x reasoning control
    ),
)
```

### Structured Output

Force agent to return typed output:

```python
from pydantic import BaseModel
from agents import Agent, Runner

class CalendarEvent(BaseModel):
    title: str
    date: str
    participants: list[str]

agent = Agent(
    name="Scheduler",
    instructions="Extract calendar events from user input",
    output_type=CalendarEvent,
)

result = Runner.run_sync(agent, "Meeting with John tomorrow at 3pm")
event: CalendarEvent = result.final_output
```

### Tool Use Behavior

Control how agent handles tool results:

```python
from agents import Agent, StopAtTools, ToolsToFinalOutputFunction

# Stop on first tool result
agent = Agent(
    name="Agent",
    tool_use_behavior="stop_on_first_tool",
)

# Stop at specific tools
agent = Agent(
    name="Agent",
    tool_use_behavior=StopAtTools(stop_at_tool_names=["final_answer"]),
)

# Custom logic
def custom_behavior(context, tool_results) -> str | None:
    for result in tool_results:
        if result.tool_name == "done":
            return result.output
    return None  # Continue LLM execution

agent = Agent(
    name="Agent",
    tool_use_behavior=ToolsToFinalOutputFunction(custom_behavior),
)
```

### Agent Cloning

Create variations of existing agents:

```python
base_agent = Agent(name="Base", instructions="...")
specialized = base_agent.clone(
    name="Specialized",
    instructions="More specific instructions",
)
```

## Best Practices

1. **Clear Instructions**: Write specific, actionable system prompts
2. **Single Responsibility**: Each agent should have one focused purpose
3. **Appropriate Handoffs**: Delegate to specialized agents for complex workflows
4. **Type Safety**: Use `output_type` for predictable structured responses
5. **Dynamic Context**: Use function-based instructions for personalization

## Additional Resources

### Reference Files

For detailed patterns and advanced configurations:
- **`references/agent-patterns.md`** - Common agent patterns and architectures
- **`references/model-configuration.md`** - Detailed model settings guide

### Example Files

Working examples in `examples/`:
- **`basic-agent.py`** - Simple agent setup
- **`dynamic-instructions.py`** - Context-aware instructions
- **`structured-output.py`** - Typed output examples
