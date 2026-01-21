---
name: OpenAI Agents SDK - Guardrails
description: This skill should be used when the user asks to "add guardrails", "validate input", "check output", "block harmful content", "detect PII", "create input guardrail", "create output guardrail", "tool guardrail", or needs guidance on @input_guardrail, @output_guardrail decorators, tripwire behavior, or content safety in OpenAI Agents SDK.
version: 1.0.0
---

# OpenAI Agents SDK - Guardrails

## Overview

Guardrails validate agent inputs and outputs to ensure safety, compliance, and quality. They can block harmful content, detect PII, enforce business rules, and more.

> **Latest Documentation**: Query Context7 MCP with Library ID `/openai/openai-agents-python` for up-to-date API references.

## Guardrail Types

| Type | Timing | Purpose |
|------|--------|---------|
| Input Guardrails | Before agent runs | Validate user input |
| Output Guardrails | After agent completes | Validate agent response |
| Tool Guardrails | Around tool execution | Validate tool I/O |

## Input Guardrails

```python
from agents import Agent, input_guardrail, GuardrailFunctionOutput, RunContextWrapper

@input_guardrail
async def check_harmful_content(
    ctx: RunContextWrapper,
    agent: Agent,
    input_text: str,
) -> GuardrailFunctionOutput:
    is_harmful = await detect_harmful(input_text)
    return GuardrailFunctionOutput(
        output_info={"checked": True, "harmful": is_harmful},
        tripwire_triggered=is_harmful,
    )

agent = Agent(
    name="SafeBot",
    input_guardrails=[check_harmful_content],
)
```

## Output Guardrails

```python
from agents import Agent, output_guardrail, GuardrailFunctionOutput

@output_guardrail
async def check_pii(
    ctx: RunContextWrapper,
    agent: Agent,
    output_text: str,
) -> GuardrailFunctionOutput:
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

## Execution Modes

```python
from agents import InputGuardrail

# Blocking mode - guardrail completes before agent starts
# Prevents token usage if input is blocked
blocking_guardrail = InputGuardrail(
    guardrail_function=check_harmful_content,
    run_in_parallel=False,
)

# Parallel mode (default) - runs with agent
# Lower latency but may waste tokens if blocked
parallel_guardrail = InputGuardrail(
    guardrail_function=check_harmful_content,
    run_in_parallel=True,
)
```

## Tool Guardrails

```python
from agents import function_tool, tool_input_guardrail, tool_output_guardrail
from agents import ToolGuardrailFunctionOutput

@tool_input_guardrail
async def validate_tool_input(ctx, agent, tool, args) -> ToolGuardrailFunctionOutput:
    if "forbidden" in str(args):
        return ToolGuardrailFunctionOutput.reject_content("Forbidden input")
    return ToolGuardrailFunctionOutput.allow()

@tool_output_guardrail
async def validate_tool_output(ctx, agent, tool, result) -> ToolGuardrailFunctionOutput:
    if "error" in result.lower():
        return ToolGuardrailFunctionOutput.reject_content("Tool error detected")
    return ToolGuardrailFunctionOutput.allow()

@function_tool(
    tool_input_guardrails=[validate_tool_input],
    tool_output_guardrails=[validate_tool_output],
)
def my_tool(data: str) -> str:
    return f"Processed: {data}"
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

1. **Blocking Mode for Safety**: Use `run_in_parallel=False` for critical checks
2. **Fast Models**: Use lightweight models for guardrail checks
3. **Informative Output**: Include details in `output_info` for debugging
4. **Layered Defense**: Combine input and output guardrails
5. **Tool Guardrails**: Protect sensitive tool operations

## Additional Resources

For the latest API references and detailed documentation, query Context7 MCP with Library ID `/openai/openai-agents-python`.
