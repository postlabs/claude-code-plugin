---
name: google-adk:dev-multi
description: Design and implement multi-agent systems in Google ADK - hierarchies, coordination patterns, communication strategies.
argument-hint: "[request]"
allowed-tools: ["Read", "Write", "Edit", "Grep", "Glob"]
---

Design and implement multi-agent systems.

## Task

Help the user create multi-agent architectures.

## Communication Patterns

### 1. Shared Session State
Agents communicate via `session.state` using output_key:
```python
researcher = Agent(
    name="researcher",
    output_key="research_findings",  # Saves to state
)
writer = Agent(
    name="writer",
    instruction="Write based on: {research_findings}",  # Reads from state
)
pipeline = SequentialAgent(sub_agents=[researcher, writer])
```

### 2. LLM-Driven Delegation
Router automatically selects sub-agents by description:
```python
support = Agent(name="support", description="Handles technical support")
billing = Agent(name="billing", description="Handles billing questions")
router = Agent(name="router", sub_agents=[support, billing])
```

### 3. Explicit AgentTool
Agent as callable tool:
```python
specialist = Agent(name="specialist", ...)
coordinator = Agent(tools=[AgentTool(agent=specialist)])
```

## Multi-Agent Patterns

### Coordinator/Dispatcher
```
        Coordinator
       /     |     \
  Finance  Legal   Tech
```

### Sequential Pipeline
```
Input → Preprocessor → Analyzer → Reporter → Output
```

### Parallel Fan-Out/Gather
```
       Dispatcher
      /    |    \
   A      B      C
      \   |   /
     Aggregator
```

### Generator-Critic Loop
```python
generator = Agent(output_key="draft")
critic = Agent(instruction="Review: {draft}. If OK, escalate=True")
loop = LoopAgent(
    sub_agent=SequentialAgent(sub_agents=[generator, critic]),
    max_iterations=3
)
```

Load the Google ADK - Multi-Agent Systems skill for complete architecture guidance.
