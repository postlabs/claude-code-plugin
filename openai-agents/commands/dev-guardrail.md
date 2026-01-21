# /openai-agent:dev-guardrail

Add input/output guardrails to agents.

## Usage

```
/openai-agent:dev-guardrail [request]
```

## Guardrail Types

### Input Guardrails
```python
@input_guardrail
async def check_input(ctx, agent, input):
    # Validate input before agent runs
    if "forbidden" in input:
        return GuardrailFunctionOutput(tripwire_triggered=True)
    return GuardrailFunctionOutput(tripwire_triggered=False)
```

### Output Guardrails
```python
@output_guardrail
async def check_output(ctx, agent, output):
    # Validate output after agent completes
    ...
```

### Tool Guardrails
- @tool_input_guardrail
- @tool_output_guardrail

## Execution Modes

- Parallel (default): Better latency
- Blocking: Prevents token use if triggered

## Examples

```
/openai-agent:dev-guardrail add PII detection guardrail
/openai-agent:dev-guardrail add content moderation
```
