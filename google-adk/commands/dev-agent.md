# /google-adk:dev-agent

Create or modify agents.

## Usage

```
/google-adk:dev-agent [request]
```

## Agent Types

### LLM Agent
Dynamic, model-driven decision-making.
```python
from google.adk import Agent

agent = Agent(
    name="assistant",
    model="gemini-2.0-flash",
    instruction="You are a helpful assistant",
    tools=[...]
)
```

### Workflow Agents
Structured execution patterns.

#### SequentialAgent
```python
from google.adk import SequentialAgent
agent = SequentialAgent(name="pipeline", sub_agents=[agent1, agent2])
```

#### ParallelAgent
```python
from google.adk import ParallelAgent
agent = ParallelAgent(name="parallel", sub_agents=[agent1, agent2])
```

#### LoopAgent
```python
from google.adk import LoopAgent
agent = LoopAgent(name="loop", sub_agent=worker, max_iterations=5)
```

### Custom Agent
```python
from google.adk import BaseAgent

class MyAgent(BaseAgent):
    async def run(self, context):
        # Custom logic
        pass
```

## Examples

```
/google-adk:dev-agent create a customer support agent
/google-adk:dev-agent create a sequential pipeline
/google-adk:dev-agent create a parallel processing agent
```
