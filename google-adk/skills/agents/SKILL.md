---
name: Google ADK - Agent Creation
description: This skill should be used when the user asks to "create an agent", "define agent instructions", "configure Gemini model", "set up output schema", "use generation config", or needs guidance on Agent class parameters, model settings, or agent configuration in Google ADK.
version: 1.0.0
---

# Google ADK - Agent Creation

## Overview

Agents are the core building blocks of Google ADK. Each agent wraps a Gemini model with instructions, tools, and optional sub-agents for complex workflows.

> **Latest Documentation**: Query Context7 MCP with Library ID `/google/adk-docs` for up-to-date API references.

## Core Concepts

### Basic Agent Creation

```python
from google.adk import Agent

agent = Agent(
    name="assistant",
    model="gemini-2.0-flash",
    description="A helpful assistant",
    instruction="You are a helpful assistant that answers questions.",
)
```

### Agent Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Agent identifier (required, important for multi-agent) |
| `model` | `str` | LLM model (e.g., "gemini-2.0-flash", "gemini-2.5-pro") |
| `description` | `str` | Agent capability summary (used for routing) |
| `instruction` | `str` | System prompt (supports dynamic templates: `{var}`) |
| `tools` | `list` | Available tools |
| `sub_agents` | `list` | Child agents for delegation |
| `input_schema` | `type` | Input schema definition |
| `output_schema` | `type` | Output schema (forces JSON) |
| `output_key` | `str` | State key for final response |
| `include_contents` | `str` | History inclusion ('default' \| 'none') |
| `generate_content_config` | `dict` | temperature, max_tokens, etc. |

### Dynamic Instructions

Use template variables in instructions:

```python
agent = Agent(
    name="personalized",
    model="gemini-2.0-flash",
    instruction="""
    You are helping {user_name}.
    Their preferences: {artifact.user_prefs}
    Current date: {current_date}
    """,
)
```

### Structured Output

Force JSON output with Pydantic models:

```python
from pydantic import BaseModel

class WeatherResponse(BaseModel):
    city: str
    temperature: float
    condition: str

agent = Agent(
    name="weather_agent",
    model="gemini-2.0-flash",
    instruction="Extract weather information",
    output_schema=WeatherResponse,
)
```

### Generation Config

Control model behavior:

```python
agent = Agent(
    name="creative_agent",
    model="gemini-2.0-flash",
    generate_content_config={
        "temperature": 0.9,
        "max_output_tokens": 2048,
        "top_p": 0.95,
        "top_k": 40,
    },
)
```

### Output Key for State

Save agent output to session state:

```python
agent = Agent(
    name="researcher",
    model="gemini-2.0-flash",
    instruction="Research the topic",
    output_key="research_findings",  # Saved to state
)

# Next agent can access via {research_findings}
```

## Supported Models

| Model | Use Case |
|-------|----------|
| `gemini-2.0-flash` | Fast, general purpose |
| `gemini-2.5-pro` | Complex reasoning |
| `gemini-2.0-flash-lite` | Cost-efficient |

## Best Practices

1. **Clear Instructions**: Write specific, actionable prompts
2. **Meaningful Names**: Use descriptive agent names for routing
3. **Output Schema**: Use for predictable structured responses
4. **State Keys**: Leverage output_key for multi-agent data flow
5. **Descriptions**: Essential for LLM-driven agent selection

## Additional Resources

For the latest API references and detailed documentation, query Context7 MCP with Library ID `/google/adk-docs`.
