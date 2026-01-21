---
name: Google ADK - Callbacks
description: This skill should be used when the user asks to "add callbacks", "use before_model_callback", "use after_model_callback", "add guardrails", "intercept tool calls", "add lifecycle hooks", or needs guidance on callback types, callback context, or event interception in Google ADK.
version: 1.0.0
---

# Google ADK - Callbacks

## Overview

Callbacks intercept agent execution at key lifecycle points, enabling validation, transformation, logging, and guardrails.

> **Latest Documentation**: Query Context7 MCP with Library ID `/google/adk-docs` for up-to-date API references.

## Callback Types

| Callback | Timing | Purpose |
|----------|--------|---------|
| `before_agent_callback` | Before agent runs | Wrap entire execution |
| `after_agent_callback` | After agent completes | Modify final output |
| `before_model_callback` | Before LLM call | Inspect/modify request, guardrails |
| `after_model_callback` | After LLM response | Sanitize/transform response |
| `before_tool_callback` | Before tool execution | Validate arguments, policies |
| `after_tool_callback` | After tool execution | Log results, post-process |

## Return Value Control

- **Return `None`**: Proceed with default behavior
- **Return value**: Replace default behavior (skip that step)

## Before Model Callback (Guardrails)

Block or modify requests before LLM call:

```python
from google.adk import Agent, CallbackContext
from google.genai.types import Content, LlmResponse, Part

def before_model_guardrail(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> LlmResponse | None:
    """Block harmful content before LLM call."""
    user_input = str(llm_request.contents[-1])

    if "forbidden_topic" in user_input.lower():
        # Return response to skip LLM call
        return LlmResponse(
            content=Content(
                parts=[Part(text="I cannot discuss that topic.")]
            )
        )

    return None  # Proceed normally

agent = Agent(
    name="safe_agent",
    model="gemini-2.0-flash",
    before_model_callback=before_model_guardrail,
)
```

## After Model Callback (Sanitization)

Transform or sanitize LLM responses:

```python
def after_model_sanitize(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> LlmResponse | None:
    """Remove PII from response."""
    response_text = str(llm_response.content)
    sanitized = remove_pii(response_text)

    if sanitized != response_text:
        return LlmResponse(
            content=Content(parts=[Part(text=sanitized)])
        )

    return None  # Use original

agent = Agent(
    name="safe_agent",
    model="gemini-2.0-flash",
    after_model_callback=after_model_sanitize,
)
```

## Before Tool Callback (Validation)

Validate tool arguments:

```python
def before_tool_validate(
    callback_context: CallbackContext,
    tool_name: str,
    tool_args: dict,
) -> dict | None:
    """Block dangerous operations."""
    if tool_name == "database_query":
        if "DROP" in tool_args.get("query", "").upper():
            return {
                "status": "error",
                "message": "Dangerous query blocked"
            }

    return None  # Proceed

agent = Agent(
    name="db_agent",
    model="gemini-2.0-flash",
    before_tool_callback=before_tool_validate,
)
```

## After Tool Callback (Logging)

Log or post-process tool results:

```python
def after_tool_log(
    callback_context: CallbackContext,
    tool_name: str,
    tool_result: dict,
) -> dict | None:
    """Log tool execution."""
    print(f"Tool {tool_name} returned: {tool_result}")
    return None  # Use original

agent = Agent(
    name="logged_agent",
    model="gemini-2.0-flash",
    after_tool_callback=after_tool_log,
)
```

## Callback Context

Access agent info and session state:

```python
def my_callback(callback_context: CallbackContext, ...):
    # Agent info
    agent_name = callback_context.agent_name

    # Read state
    user_id = callback_context.state.get("user_id")

    # Update state
    callback_context.state["last_action"] = "callback_executed"
```

## Complete Example

```python
from google.adk import Agent, CallbackContext

agent = Agent(
    name="safe_agent",
    model="gemini-2.0-flash",
    instruction="You are a helpful assistant",
    before_model_callback=before_model_guardrail,
    after_model_callback=after_model_sanitize,
    before_tool_callback=before_tool_validate,
    after_tool_callback=after_tool_log,
)
```

## Best Practices

1. **Guardrails**: Use before_model_callback for input validation
2. **Sanitization**: Use after_model_callback for PII removal
3. **Logging**: Use after_tool_callback for observability
4. **Return None**: When no modification needed
5. **Keep Fast**: Callbacks should be quick to avoid latency

## Additional Resources

For the latest API references and detailed documentation, query Context7 MCP with Library ID `/google/adk-docs`.
