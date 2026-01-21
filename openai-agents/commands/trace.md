# /openai-agent:trace

Configure and view execution traces.

## Usage

```
/openai-agent:trace [request]
```

## Tracing Features

### Auto-tracing (Default)
- LLM generations
- Tool calls
- Handoffs
- Guardrails

### Custom Traces
```python
from agents import trace

with trace("My Workflow"):
    # Your code here
    pass
```

### Configuration
```python
RunConfig(
    tracing_disabled=False,
    trace_include_sensitive_data=False
)
```

## View Traces

Traces are available at: https://platform.openai.com/traces

## Examples

```
/openai-agent:trace disable tracing for this agent
/openai-agent:trace add custom trace for data processing
/openai-agent:trace configure sensitive data protection
```
