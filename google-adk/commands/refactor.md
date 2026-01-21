---
description: Refactor Google ADK agent code for better structure, maintainability, and best practices.
argument-hint: "[request]"
allowed-tools: ["Read", "Write", "Edit", "Grep", "Glob"]
---

Refactor Google ADK agent code.

## Task

Improve the structure and maintainability of agent code.

## Common Refactoring Tasks

### Split Large Agents
Convert monolithic agent to specialized agents:

**Before:**
```python
agent = Agent(
    name="do_everything",
    instruction="Handle support, billing, and technical questions...",
    tools=[support_tool, billing_tool, tech_tool],
)
```

**After:**
```python
support = Agent(name="support", description="Technical support", ...)
billing = Agent(name="billing", description="Billing questions", ...)
tech = Agent(name="tech", description="Technical issues", ...)

coordinator = Agent(
    name="coordinator",
    instruction="Route to appropriate specialist",
    sub_agents=[support, billing, tech],
)
```

### Convert to Multi-Agent Architecture
Use workflow agents for complex flows:
```python
# Sequential pipeline
pipeline = SequentialAgent(
    name="pipeline",
    sub_agents=[preprocessor, analyzer, reporter],
)

# Parallel processing
parallel = ParallelAgent(
    name="parallel",
    sub_agents=[searcher1, searcher2, searcher3],
)
```

### Extract Reusable Tools
Move inline logic to reusable tools:

**Before:**
```python
# Logic in instruction
agent = Agent(instruction="When user asks for weather, use the API at...")
```

**After:**
```python
def get_weather(city: str) -> dict:
    """Get weather for a city."""
    # Clean, reusable implementation
    ...

agent = Agent(tools=[get_weather])
```

### Add Type Hints and Docstrings
Ensure all tools are properly documented:
```python
def my_tool(param: str, optional: int = 10) -> dict:
    """Clear description for LLM.

    Args:
        param: What this parameter does
        optional: Optional parameter with default

    Returns:
        Dictionary with status and data
    """
```

## Process

1. Analyze current code structure
2. Identify refactoring opportunities
3. Plan changes to minimize disruption
4. Implement improvements incrementally
5. Verify functionality after each change
