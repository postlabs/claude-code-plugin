# /google-adk:dev-multi

Configure multi-agent systems.

## Usage

```
/google-adk:dev-multi [request]
```

## Multi-Agent Patterns

### Hierarchical
```python
# Router delegates to specialists
router = Agent(
    name="router",
    sub_agents=[support_agent, billing_agent, sales_agent]
)
```

### Sequential Pipeline
```python
pipeline = SequentialAgent(
    name="pipeline",
    sub_agents=[
        data_collector,
        analyzer,
        reporter
    ]
)
```

### Parallel Processing
```python
parallel = ParallelAgent(
    name="parallel",
    sub_agents=[
        web_searcher,
        doc_searcher,
        db_searcher
    ]
)
```

### Mixed Architecture
```python
# Combine patterns
main = Agent(
    name="main",
    sub_agents=[
        SequentialAgent(...),
        ParallelAgent(...),
        specialist_agent
    ]
)
```

## Examples

```
/google-adk:dev-multi create router with 3 specialist agents
/google-adk:dev-multi create data processing pipeline
/google-adk:dev-multi combine sequential and parallel agents
```
