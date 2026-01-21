---
name: openai-agents:trace
description: Configure and view execution traces for debugging
argument-hint: [request]
allowed-tools: Read, Write, Edit, Grep, Glob
---

Configure tracing for agents: $ARGUMENTS

## Tracing Overview

Tracing is enabled by default and captures:
- Runner execution
- Agent execution
- LLM generations
- Tool calls
- Guardrails
- Handoffs

**View traces at**: https://platform.openai.com/traces

## Custom Traces

```python
from agents import trace, custom_span

with trace("MyWorkflow", group_id="user_123"):
    # Custom span
    with custom_span("preprocessing"):
        data = preprocess(input_data)

    # Agent execution (auto-traced)
    result = await Runner.run(agent, data)

    with custom_span("postprocessing"):
        output = postprocess(result)
```

## RunConfig Tracing Options

```python
from agents import RunConfig

config = RunConfig(
    # Disable tracing
    tracing_disabled=False,

    # Workflow identification
    workflow_name="CustomerSupport",
    trace_id="trace_123",
    group_id="user_456",

    # Privacy
    trace_include_sensitive_data=False,
)
```

## Disable Tracing

```python
# Per-run
config = RunConfig(tracing_disabled=True)

# Environment variable
# OPENAI_AGENTS_DISABLE_TRACING=1

# Global
from agents import set_tracing_disabled
set_tracing_disabled(True)
```

## Sensitive Data Protection

```python
# Per-run
config = RunConfig(trace_include_sensitive_data=False)

# Environment variable
# OPENAI_AGENTS_TRACE_INCLUDE_SENSITIVE_DATA=false
```

## Non-OpenAI Model Tracing

When using LiteLLM with non-OpenAI models:

```python
from agents import set_tracing_export_api_key

# Export traces to OpenAI for viewing
set_tracing_export_api_key("sk-openai-key")
```

## Custom Processors

```python
from agents import add_trace_processor, set_trace_processors

# Add processor
add_trace_processor(my_processor)

# Replace processors
set_trace_processors([my_processor])
```

## Verbose Logging

```python
from agents import enable_verbose_stdout_logging

enable_verbose_stdout_logging()
```

## Best Practices

1. **Use Group IDs**: Group traces by user/session
2. **Custom Spans**: Mark important steps
3. **Protect Data**: Disable sensitive data in production
4. **Review Regularly**: Check traces for issues
5. **External Tools**: Integrate with monitoring platforms

## Implementation

Configure tracing as requested.
Set appropriate privacy settings for the use case.
