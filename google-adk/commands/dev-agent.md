---
name: google-adk:dev-agent
description: Create or modify Google ADK agents - LLM agents, workflow agents (Sequential, Parallel, Loop), or custom agents.
argument-hint: "[request]"
allowed-tools: ["Read", "Write", "Edit", "Grep", "Glob"]
---

Create or modify agents using Google ADK.

## Task

Help the user create or modify agents based on their requirements.

## Agent Types

### LLM Agent (Default)
Dynamic, model-driven decision-making:
```python
from google.adk import Agent

agent = Agent(
    name="assistant",
    model="gemini-2.0-flash",
    instruction="You are a helpful assistant",
    description="General assistant for user queries",  # For routing
    tools=[...],
    sub_agents=[...],  # Optional delegation
)
```

### Workflow Agents
Structured execution patterns:

**SequentialAgent** - Execute in order:
```python
from google.adk import SequentialAgent
pipeline = SequentialAgent(name="pipeline", sub_agents=[step1, step2, step3])
```

**ParallelAgent** - Execute concurrently:
```python
from google.adk import ParallelAgent
parallel = ParallelAgent(name="parallel", sub_agents=[task1, task2, task3])
```

**LoopAgent** - Iterate until condition:
```python
from google.adk import LoopAgent
loop = LoopAgent(name="loop", sub_agent=worker, max_iterations=5)
```

### Custom Agent
For complex logic:
```python
from google.adk import BaseAgent

class MyAgent(BaseAgent):
    async def run(self, context):
        # Custom implementation
        pass
```

## Key Parameters

- **name**: Required identifier
- **model**: LLM model to use (gemini-2.0-flash, etc.)
- **instruction**: System prompt for the agent
- **description**: Used for routing in multi-agent systems
- **tools**: List of available tools
- **sub_agents**: Child agents for delegation
- **output_key**: Save output to session state

Load the Google ADK - Agent Creation skill for complete configuration details.
