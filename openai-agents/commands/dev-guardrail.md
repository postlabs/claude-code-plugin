---
description: Add input/output guardrails for agent safety
argument-hint: [request]
allowed-tools: Read, Write, Edit, Grep, Glob
---

Add guardrails to agents: $ARGUMENTS

## Guardrail Types

### Input Guardrails

```python
from agents import Agent, input_guardrail, GuardrailFunctionOutput

@input_guardrail
async def check_harmful(ctx, agent, input_text) -> GuardrailFunctionOutput:
    is_harmful = await detect_harmful_content(input_text)
    return GuardrailFunctionOutput(
        output_info={"checked": True, "harmful": is_harmful},
        tripwire_triggered=is_harmful,
    )

agent = Agent(
    name="SafeBot",
    input_guardrails=[check_harmful],
)
```

### Output Guardrails

```python
from agents import output_guardrail, GuardrailFunctionOutput

@output_guardrail
async def check_pii(ctx, agent, output_text) -> GuardrailFunctionOutput:
    has_pii = detect_pii(output_text)
    return GuardrailFunctionOutput(
        output_info={"pii_detected": has_pii},
        tripwire_triggered=has_pii,
    )

agent = Agent(
    name="SafeBot",
    output_guardrails=[check_pii],
)
```

### Tool Guardrails

```python
from agents import function_tool, tool_input_guardrail, tool_output_guardrail
from agents import ToolGuardrailFunctionOutput

@tool_input_guardrail
async def validate_input(ctx, agent, tool, args):
    if "forbidden" in str(args):
        return ToolGuardrailFunctionOutput.reject_content("Forbidden input")
    return ToolGuardrailFunctionOutput.allow()

@function_tool(tool_input_guardrails=[validate_input])
def my_tool(data: str) -> str:
    return f"Processed: {data}"
```

## Execution Modes

```python
from agents import InputGuardrail

# Blocking - prevents token usage if blocked
blocking = InputGuardrail(
    guardrail_function=check_harmful,
    run_in_parallel=False,  # Waits for guardrail
)

# Parallel - lower latency, may waste tokens
parallel = InputGuardrail(
    guardrail_function=check_harmful,
    run_in_parallel=True,  # Default
)
```

## Exception Handling

```python
from agents import (
    Runner,
    InputGuardrailTripwireTriggered,
    OutputGuardrailTripwireTriggered,
)

try:
    result = await Runner.run(agent, user_input)
except InputGuardrailTripwireTriggered as e:
    print(f"Input blocked: {e.guardrail_result.output_info}")
except OutputGuardrailTripwireTriggered as e:
    print(f"Output blocked: {e.guardrail_result.output_info}")
```

## Best Practices

1. **Blocking for Safety**: Use run_in_parallel=False for critical checks
2. **Fast Models**: Use lightweight models in guardrails
3. **Informative Output**: Include details in output_info
4. **Layered Defense**: Combine input and output guardrails
5. **Tool Protection**: Add guardrails to sensitive tools

## Implementation

Create the requested guardrails.
Ensure proper async patterns and exception handling.
