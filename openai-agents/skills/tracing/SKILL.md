---
name: OpenAI Agents SDK - Tracing
description: This skill should be used when the user asks to "add tracing", "debug agent", "view traces", "configure logging", "disable tracing", "protect sensitive data", "custom trace span", or needs guidance on trace configuration, trace processors, or debugging agent execution in OpenAI Agents SDK.
version: 1.0.0
---

# OpenAI Agents SDK - Tracing

## Overview

Tracing provides visibility into agent execution for debugging, monitoring, and optimization. OpenAI Agents SDK automatically traces agent runs, tool calls, handoffs, and guardrails.

> **Latest Documentation**: Query Context7 MCP with Library ID `/openai/openai-agents-python` for up-to-date API references.

## Default Tracing

Tracing is enabled by default and captures:
- Runner execution
- Agent execution
- LLM generations
- Tool calls
- Guardrails
- Handoffs

View traces at: https://platform.openai.com/traces

## Custom Traces

```python
from agents import trace, custom_span, generation_span

with trace("MyWorkflow", group_id="user_123"):
    # Custom span for preprocessing
    with custom_span("preprocessing"):
        data = preprocess(input_data)

    # Agent execution (automatically traced)
    result = await Runner.run(agent, data)

    # Custom span for postprocessing
    with custom_span("postprocessing"):
        output = postprocess(result)
```

## RunConfig Tracing Options

```python
from agents import RunConfig

config = RunConfig(
    # Disable tracing for this run
    tracing_disabled=False,

    # Workflow name for grouping
    workflow_name="CustomerSupport",

    # Custom trace ID
    trace_id="trace_123",

    # Group related traces
    group_id="user_456",

    # Exclude sensitive data from traces
    trace_include_sensitive_data=False,
)

result = await Runner.run(agent, "Hello", run_config=config)
```

## Disable Tracing

```python
# Via RunConfig (per-run)
config = RunConfig(tracing_disabled=True)

# Via environment variable (global)
# OPENAI_AGENTS_DISABLE_TRACING=1

# Via function call (global)
from agents import set_tracing_disabled
set_tracing_disabled(True)
```

## Sensitive Data Protection

```python
# Via RunConfig
config = RunConfig(trace_include_sensitive_data=False)

# Via environment variable
# OPENAI_AGENTS_TRACE_INCLUDE_SENSITIVE_DATA=false
```

## Non-OpenAI Model Tracing

When using non-OpenAI models (via LiteLLM), export traces to OpenAI:

```python
from agents import set_tracing_export_api_key

set_tracing_export_api_key("sk-openai-key-for-tracing")
```

## Custom Trace Processors

```python
from agents import add_trace_processor, set_trace_processors

# Add additional processor
add_trace_processor(my_custom_processor)

# Replace all processors
set_trace_processors([my_processor])
```

## Verbose Logging

```python
from agents import enable_verbose_stdout_logging

# Enable detailed console output
enable_verbose_stdout_logging()
```

## External Integrations

OpenAI tracing integrates with 20+ platforms:
- Weights & Biases
- Arize-Phoenix
- MLflow
- Braintrust
- Pydantic Logfire
- AgentOps
- LangSmith
- Langfuse

## Best Practices

1. **Use Group IDs**: Group related traces by user or session
2. **Custom Spans**: Mark important processing steps
3. **Protect Data**: Disable sensitive data in production
4. **Review Traces**: Regularly check for issues
5. **External Tools**: Integrate with monitoring platforms

## Additional Resources

For the latest API references and detailed documentation, query Context7 MCP with Library ID `/openai/openai-agents-python`.
