---
name: Google ADK - Multi-Agent Systems
description: This skill should be used when the user asks to "create multi-agent system", "configure sub_agents", "set up agent routing", "use transfer_to_agent", "design agent hierarchy", or needs guidance on agent communication, coordination patterns, or hierarchical agent structures in Google ADK.
version: 1.0.0
---

# Google ADK - Multi-Agent Systems

## Overview

Multi-agent systems combine multiple specialized agents for complex tasks. Google ADK supports hierarchical structures where agents can delegate to sub-agents.

> **Latest Documentation**: Query Context7 MCP with Library ID `/google/adk-docs` for up-to-date API references.

## Communication Patterns

### 1. Shared Session State

Agents communicate via `session.state`:

```python
from google.adk import Agent, SequentialAgent

researcher = Agent(
    name="researcher",
    model="gemini-2.0-flash",
    instruction="Research and save findings",
    output_key="research_findings",  # Save to state
)

writer = Agent(
    name="writer",
    model="gemini-2.0-flash",
    instruction="Write based on: {research_findings}",  # Read from state
)

pipeline = SequentialAgent(
    name="content_pipeline",
    sub_agents=[researcher, writer],
)
```

### 2. LLM-Driven Delegation

Router agent automatically selects sub-agents:

```python
support_agent = Agent(
    name="support",
    model="gemini-2.0-flash",
    description="Handles technical support questions",
    instruction="Handle technical support",
)

billing_agent = Agent(
    name="billing",
    model="gemini-2.0-flash",
    description="Handles billing and payment questions",
    instruction="Handle billing inquiries",
)

# Router uses descriptions to choose
router = Agent(
    name="router",
    model="gemini-2.0-flash",
    instruction="Route user to appropriate department",
    sub_agents=[support_agent, billing_agent],
)
```

### 3. Explicit AgentTool

Agent as callable tool:

```python
from google.adk import Agent, AgentTool

specialist = Agent(
    name="specialist",
    model="gemini-2.0-flash",
    instruction="You are an expert analyst",
)

coordinator = Agent(
    name="coordinator",
    model="gemini-2.0-flash",
    instruction="Coordinate work and use specialist when needed",
    tools=[AgentTool(agent=specialist)],
)
```

## Multi-Agent Patterns

### Coordinator/Dispatcher

```python
specialists = [
    Agent(name="finance", description="Financial analysis", ...),
    Agent(name="legal", description="Legal questions", ...),
    Agent(name="tech", description="Technical support", ...),
]

coordinator = Agent(
    name="coordinator",
    model="gemini-2.0-flash",
    instruction="Route requests to appropriate specialist",
    sub_agents=specialists,
)
```

### Sequential Pipeline

```python
from google.adk import SequentialAgent

pipeline = SequentialAgent(
    name="document_pipeline",
    sub_agents=[
        Agent(name="extractor", instruction="Extract key info", output_key="extracted"),
        Agent(name="analyzer", instruction="Analyze: {extracted}", output_key="analysis"),
        Agent(name="summarizer", instruction="Summarize: {analysis}"),
    ],
)
```

### Parallel Fan-Out/Gather

```python
from google.adk import ParallelAgent, SequentialAgent

parallel_research = ParallelAgent(
    name="parallel_research",
    sub_agents=[
        Agent(name="web", output_key="web_data", ...),
        Agent(name="db", output_key="db_data", ...),
        Agent(name="api", output_key="api_data", ...),
    ],
)

gatherer = Agent(
    name="gatherer",
    instruction="Combine: {web_data}, {db_data}, {api_data}",
)

pipeline = SequentialAgent(
    name="research_pipeline",
    sub_agents=[parallel_research, gatherer],
)
```

### Generator-Critic Loop

```python
from google.adk import LoopAgent, SequentialAgent

generator = Agent(
    name="generator",
    instruction="Generate content",
    output_key="draft",
)

critic = Agent(
    name="critic",
    instruction="""
    Review the draft: {draft}
    If acceptable, respond with escalate=True.
    Otherwise, provide feedback.
    """,
    output_key="feedback",
)

refinement = LoopAgent(
    name="refinement",
    sub_agent=SequentialAgent(
        name="gen_crit",
        sub_agents=[generator, critic],
    ),
    max_iterations=3,
)
```

## Hierarchical Structure

```
                    Coordinator
                    /    |    \
               Finance  Legal  Tech
              /    \
          Analysis  Report
```

```python
# Level 2 specialists
analysis = Agent(name="analysis", ...)
report = Agent(name="report", ...)

# Level 1 departments
finance = Agent(
    name="finance",
    sub_agents=[analysis, report],
)
legal = Agent(name="legal", ...)
tech = Agent(name="tech", ...)

# Level 0 coordinator
coordinator = Agent(
    name="coordinator",
    sub_agents=[finance, legal, tech],
)
```

## Best Practices

1. **Single Responsibility**: Each agent has one focused role
2. **Clear Descriptions**: Essential for LLM-driven routing
3. **Use output_key**: For state-based communication
4. **Appropriate Patterns**: Match pattern to task structure
5. **Limit Depth**: Avoid overly deep hierarchies

## Additional Resources

For the latest API references and detailed documentation, query Context7 MCP with Library ID `/google/adk-docs`.
