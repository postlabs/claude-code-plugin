# Model Configuration Reference

## Supported Models

### OpenAI Models (Default)

```python
from agents import Agent

# GPT-4.1 (default, recommended)
agent = Agent(name="Bot", model="gpt-4.1")

# GPT-5.x (highest quality)
agent = Agent(name="Bot", model="gpt-5.2")

# GPT-4.1-mini (faster, cheaper)
agent = Agent(name="Bot", model="gpt-4.1-mini")
```

### LiteLLM Integration

Install with extras:
```bash
pip install openai-agents[litellm]
```

```python
from agents import Agent

# Claude
agent = Agent(
    name="ClaudeBot",
    model="litellm/anthropic/claude-3-5-sonnet-20240620",
)

# Gemini
agent = Agent(
    name="GeminiBot",
    model="litellm/gemini/gemini-2.5-flash-preview-04-17",
)

# Custom OpenAI-compatible endpoint
agent = Agent(
    name="CustomBot",
    model="litellm/openai/my-model",
)
```

## ModelSettings Parameters

```python
from agents import ModelSettings

settings = ModelSettings(
    # Temperature: 0.0 (deterministic) to 2.0 (creative)
    temperature=0.7,

    # Top-p sampling (nucleus sampling)
    top_p=0.9,

    # Tool choice behavior
    tool_choice="auto",  # "auto" | "required" | "none" | {"type": "function", "function": {"name": "..."}}

    # Max tokens in response
    max_tokens=4096,

    # Frequency penalty: -2.0 to 2.0
    frequency_penalty=0.0,

    # Presence penalty: -2.0 to 2.0
    presence_penalty=0.0,

    # Stop sequences
    stop=["END", "DONE"],

    # GPT-5.x reasoning effort
    reasoning={"effort": "medium"},  # "none" | "low" | "medium" | "high"
)
```

## API Selection

```python
from agents import set_default_openai_api

# Responses API (default, recommended)
# Supports: conversation memory, server-managed state
set_default_openai_api("responses")

# Chat Completions API
# Use when: custom clients, specific API requirements
set_default_openai_api("chat_completions")
```

## Custom Client Configuration

```python
from agents import set_default_openai_client, set_default_openai_key
from openai import AsyncOpenAI

# Set API key
set_default_openai_key("sk-...")

# Custom client with different endpoint
client = AsyncOpenAI(
    base_url="https://my-proxy.example.com/v1",
    api_key="my-key",
)
set_default_openai_client(client)
```

## Model Selection Guidelines

| Use Case | Recommended Model | Reason |
|----------|-------------------|--------|
| General tasks | `gpt-4.1` | Good balance of quality and speed |
| Complex reasoning | `gpt-5.2` | Best reasoning capabilities |
| High volume | `gpt-4.1-mini` | Faster, lower cost |
| Non-OpenAI | `litellm/...` | Provider flexibility |

## Reasoning Configuration (GPT-5.x)

```python
from agents import Agent, ModelSettings

# No reasoning (fastest)
agent = Agent(
    model="gpt-5.2",
    model_settings=ModelSettings(reasoning={"effort": "none"}),
)

# Low reasoning (balanced)
agent = Agent(
    model="gpt-5.2",
    model_settings=ModelSettings(reasoning={"effort": "low"}),
)

# Medium reasoning (recommended)
agent = Agent(
    model="gpt-5.2",
    model_settings=ModelSettings(reasoning={"effort": "medium"}),
)

# High reasoning (most thorough)
agent = Agent(
    model="gpt-5.2",
    model_settings=ModelSettings(reasoning={"effort": "high"}),
)
```

## Environment Variables

```bash
# OpenAI API key
OPENAI_API_KEY=sk-...

# Disable tracing
OPENAI_AGENTS_DISABLE_TRACING=1

# Sensitive data in traces
OPENAI_AGENTS_TRACE_INCLUDE_SENSITIVE_DATA=false
```
