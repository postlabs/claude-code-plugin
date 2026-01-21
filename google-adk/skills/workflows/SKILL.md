---
name: Google ADK - Workflow Agents
description: This skill should be used when the user asks to "create a pipeline", "use SequentialAgent", "use ParallelAgent", "use LoopAgent", "create workflow", "chain agents", or needs guidance on workflow patterns, sequential execution, parallel processing, or iterative loops in Google ADK.
version: 1.0.0
---

# Google ADK - Workflow Agents

## Overview

Workflow agents provide structured execution patterns for complex multi-step tasks. Unlike LLM agents that use dynamic reasoning, workflow agents follow predefined patterns.

> **Latest Documentation**: Query Context7 MCP with Library ID `/google/adk-docs` for up-to-date API references.

## Workflow Types

| Type | Pattern | Use Case |
|------|---------|----------|
| SequentialAgent | A → B → C | Pipelines, step-by-step |
| ParallelAgent | A, B, C (concurrent) | Fan-out, gather |
| LoopAgent | A → A → A (repeat) | Refinement, iteration |

## SequentialAgent

Execute sub-agents in order. Each agent's output flows to the next:

```python
from google.adk import SequentialAgent, Agent

data_fetcher = Agent(
    name="data_fetcher",
    model="gemini-2.0-flash",
    instruction="Fetch relevant data",
    output_key="fetched_data",  # Save to state
)

analyzer = Agent(
    name="analyzer",
    model="gemini-2.0-flash",
    instruction="Analyze the data: {fetched_data}",  # Read from state
    output_key="analysis",
)

reporter = Agent(
    name="reporter",
    model="gemini-2.0-flash",
    instruction="Generate report from analysis: {analysis}",
)

pipeline = SequentialAgent(
    name="data_pipeline",
    sub_agents=[data_fetcher, analyzer, reporter],
)
```

## ParallelAgent

Execute sub-agents concurrently. All agents share `session.state`:

```python
from google.adk import ParallelAgent, Agent

web_searcher = Agent(
    name="web_searcher",
    model="gemini-2.0-flash",
    instruction="Search the web",
    output_key="web_results",
)

doc_searcher = Agent(
    name="doc_searcher",
    model="gemini-2.0-flash",
    instruction="Search documents",
    output_key="doc_results",
)

db_searcher = Agent(
    name="db_searcher",
    model="gemini-2.0-flash",
    instruction="Query database",
    output_key="db_results",
)

parallel_search = ParallelAgent(
    name="parallel_search",
    sub_agents=[web_searcher, doc_searcher, db_searcher],
)

# Aggregator after parallel
aggregator = Agent(
    name="aggregator",
    model="gemini-2.0-flash",
    instruction="""
    Combine results:
    - Web: {web_results}
    - Docs: {doc_results}
    - DB: {db_results}
    """,
)

# Full pipeline
full_pipeline = SequentialAgent(
    name="search_pipeline",
    sub_agents=[parallel_search, aggregator],
)
```

## LoopAgent

Repeat until condition or max iterations:

```python
from google.adk import LoopAgent, Agent

refiner = Agent(
    name="refiner",
    model="gemini-2.0-flash",
    instruction="""
    Review and improve the content.
    If satisfied, respond with escalate=True.
    Current content: {draft}
    """,
    output_key="draft",
)

refinement_loop = LoopAgent(
    name="refinement_loop",
    sub_agent=refiner,
    max_iterations=5,
)
```

## Common Patterns

### Fan-Out/Gather

```python
# Parallel research + aggregation
pipeline = SequentialAgent(
    name="research_pipeline",
    sub_agents=[
        ParallelAgent(
            name="parallel_research",
            sub_agents=[researcher1, researcher2, researcher3],
        ),
        aggregator,
    ],
)
```

### Generator-Critic Loop

```python
generator = Agent(name="generator", output_key="draft", ...)
critic = Agent(
    name="critic",
    instruction="Review: {draft}. If OK, escalate=True",
    output_key="feedback",
)

gen_crit_loop = LoopAgent(
    name="gen_crit",
    sub_agent=SequentialAgent(
        name="gen_crit_seq",
        sub_agents=[generator, critic],
    ),
    max_iterations=3,
)
```

### Nested Workflows

```python
# Complex multi-level pipeline
main_pipeline = SequentialAgent(
    name="main",
    sub_agents=[
        preprocessor,
        ParallelAgent(
            name="parallel_processing",
            sub_agents=[
                SequentialAgent(name="path_a", sub_agents=[a1, a2]),
                SequentialAgent(name="path_b", sub_agents=[b1, b2]),
            ],
        ),
        aggregator,
        postprocessor,
    ],
)
```

## State Flow with output_key

```python
agent1 = Agent(
    name="step1",
    instruction="Process input",
    output_key="step1_result",  # state["step1_result"] = output
)

agent2 = Agent(
    name="step2",
    instruction="Continue from: {step1_result}",  # Reads state
    output_key="step2_result",
)
```

## Best Practices

1. **Use output_key**: Essential for data flow between agents
2. **Descriptive Names**: Clear agent names for debugging
3. **Parallel When Possible**: Independent tasks should run concurrently
4. **Max Iterations**: Always set limits on LoopAgent
5. **Combine Patterns**: Nest workflows for complex logic

## Additional Resources

For the latest API references and detailed documentation, query Context7 MCP with Library ID `/google/adk-docs`.
