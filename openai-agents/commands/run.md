# /openai-agent:run

Run and test agents.

## Usage

```
/openai-agent:run [agent-file] [prompt]
```

## Examples

```
/openai-agent:run agents/main_agent.py "Hello, help me with my order"
/openai-agent:run  # Interactive mode
```

## Run Options

```python
from agents import Runner

# Sync
result = Runner.run_sync(agent, "prompt")

# Async
result = await Runner.run(agent, "prompt")

# With config
result = Runner.run_sync(agent, "prompt", run_config=RunConfig(...))
```
