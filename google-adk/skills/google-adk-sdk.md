# Google ADK Knowledge

This skill provides comprehensive knowledge about the Google Agent Development Kit.

## Overview

The Google ADK is a flexible framework for building AI agents with:
- **LLM Agents**: Dynamic, model-driven decision-making
- **Workflow Agents**: Sequential, Parallel, Loop patterns
- **Multi-Agent Systems**: Hierarchical agent composition
- **Rich Tool Ecosystem**: Pre-built and custom tools
- **Callbacks**: Lifecycle event hooks
- **Deployment**: Vertex AI, Cloud Run, Docker

## Core Concepts

### Agent Creation
```python
from google.adk import Agent

agent = Agent(
    name="assistant",
    model="gemini-2.0-flash",
    instruction="You are a helpful assistant",
    tools=[...],
    sub_agents=[...]
)
```

### Agent Types

#### LLM Agent
```python
agent = Agent(name="smart", model="gemini-2.0-flash", ...)
```

#### Sequential Agent
```python
from google.adk import SequentialAgent
pipeline = SequentialAgent(name="pipeline", sub_agents=[a1, a2, a3])
```

#### Parallel Agent
```python
from google.adk import ParallelAgent
parallel = ParallelAgent(name="parallel", sub_agents=[a1, a2])
```

#### Loop Agent
```python
from google.adk import LoopAgent
loop = LoopAgent(name="loop", sub_agent=worker, max_iterations=5)
```

### Tools

#### Function Tool
```python
from google.adk import FunctionTool

def my_func(arg: str) -> str:
    return f"Result: {arg}"

tool = FunctionTool(func=my_func)
```

#### Pre-built Tools
- Google Search, Code Execution
- BigQuery, Spanner, Vertex AI Search
- GitHub, Asana, Notion, Stripe

### Callbacks
```python
def before_agent(context, agent, request):
    print(f"Agent {agent.name} starting")
    return None

agent = Agent(
    ...,
    before_agent_callback=before_agent
)
```

### Deployment
```bash
# Vertex AI
adk deploy vertex-ai --project=my-project

# Cloud Run
adk deploy cloud-run --project=my-project

# Docker
adk build docker
```

## Best Practices

1. Use appropriate agent type for the task
2. Combine agents for complex workflows
3. Add callbacks for observability
4. Write test cases for evaluation
5. Use environment-specific configurations
