---
name: google-adk:dev-callback
description: Configure callbacks for Google ADK agent lifecycle events - guardrails, sanitization, logging, validation.
argument-hint: "[request]"
allowed-tools: ["Read", "Write", "Edit", "Grep", "Glob"]
---

Configure callbacks for agent lifecycle events.

## Task

Help the user implement callbacks for their agents.

## Callback Types

| Callback | Timing | Purpose |
|----------|--------|---------|
| before_model_callback | Before LLM call | Guardrails, input validation |
| after_model_callback | After LLM response | Sanitization, transformation |
| before_tool_callback | Before tool execution | Argument validation, policies |
| after_tool_callback | After tool execution | Logging, post-processing |

## Return Value Control

- **Return None**: Proceed with default behavior
- **Return value**: Replace default (skip that step)

## Examples

### Guardrail (Block harmful content)
```python
def before_model_guardrail(callback_context, llm_request):
    user_input = str(llm_request.contents[-1])
    if "forbidden" in user_input.lower():
        return LlmResponse(
            content=Content(parts=[Part(text="I cannot discuss that.")])
        )
    return None  # Proceed normally

agent = Agent(before_model_callback=before_model_guardrail)
```

### Logging
```python
def after_tool_log(callback_context, tool_name, tool_result):
    print(f"Tool {tool_name} returned: {tool_result}")
    return None  # Use original result

agent = Agent(after_tool_callback=after_tool_log)
```

### Tool Validation
```python
def before_tool_validate(callback_context, tool_name, tool_args):
    if tool_name == "database_query":
        if "DROP" in tool_args.get("query", "").upper():
            return {"status": "error", "message": "Dangerous query blocked"}
    return None  # Proceed

agent = Agent(before_tool_callback=before_tool_validate)
```

Load the Google ADK - Callbacks skill for complete callback patterns.
