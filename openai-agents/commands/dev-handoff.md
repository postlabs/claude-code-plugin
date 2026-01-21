# /openai-agent:dev-handoff

Configure handoffs between agents.

## Usage

```
/openai-agent:dev-handoff [request]
```

## Handoff Configuration

```python
from agents import Agent, handoff

support_agent = Agent(name="Support", ...)
billing_agent = Agent(name="Billing", ...)

main_agent = Agent(
    name="Router",
    handoffs=[
        handoff(agent=support_agent, tool_description="Transfer to support"),
        handoff(agent=billing_agent, tool_description="Transfer to billing"),
    ]
)
```

## Options

- tool_name_override: Custom tool name
- tool_description_override: Custom description
- on_handoff: Callback when handoff occurs
- input_type: Structured input via Pydantic
- input_filter: Filter data before handoff

## Examples

```
/openai-agent:dev-handoff add handoff to billing agent
/openai-agent:dev-handoff configure input filter for handoff
```
