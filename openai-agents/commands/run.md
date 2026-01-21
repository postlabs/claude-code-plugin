---
name: openai-agents:run
description: Run and test agents interactively
argument-hint: [agent-file] [prompt]
allowed-tools: Read, Bash(python:*)
---

Run an OpenAI Agent SDK agent: $ARGUMENTS

## Running Agents

### Basic Execution

```python
from agents import Agent, Runner

agent = Agent(name="Bot", instructions="...")

# Synchronous
result = Runner.run_sync(agent, "Hello")
print(result.final_output)

# Asynchronous
result = await Runner.run(agent, "Hello")
```

### With RunConfig

```python
from agents import RunConfig, ModelSettings

config = RunConfig(
    model="gpt-5.2",
    model_settings=ModelSettings(temperature=0.7),
    max_turns=10,
    tracing_disabled=False,
    workflow_name="MyWorkflow",
)

result = await Runner.run(agent, "Hello", run_config=config)
```

### Streaming

```python
async with Runner.run_streamed(agent, "Hello") as stream:
    async for event in stream.stream_events():
        if event.type == "raw_response_event":
            print(event.data)
```

### With Session

```python
from agents.extensions.session import SQLiteSession

session = SQLiteSession(session_id="user_123")
result = await Runner.run(agent, "Hello", session=session)
result = await Runner.run(agent, "Follow up", session=session)
```

## RunResult Properties

| Property | Description |
|----------|-------------|
| `final_output` | Agent's final response |
| `response_id` | ID for conversation continuation |
| `to_input_list()` | Convert to input for next run |
| `all_tool_calls` | List of tool calls made |

## Error Handling

```python
from agents import (
    MaxTurnsExceeded,
    ModelBehaviorError,
    InputGuardrailTripwireTriggered,
    OutputGuardrailTripwireTriggered,
)

try:
    result = await Runner.run(agent, input_text)
except MaxTurnsExceeded:
    print("Too many turns")
except ModelBehaviorError as e:
    print(f"Model error: {e}")
```

## Implementation

If an agent file is specified, load and run it.
If no file specified, look for main agent in project.
Execute with the provided prompt and display results.
