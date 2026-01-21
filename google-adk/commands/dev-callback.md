# /google-adk:dev-callback

Configure callbacks for agent lifecycle events.

## Usage

```
/google-adk:dev-callback [request]
```

## Callback Types

### Before/After Agent
```python
def before_agent(context, agent, request):
    # Run before agent processes request
    return None  # Continue normally

def after_agent(context, agent, response):
    # Run after agent completes
    return None  # Use response as-is
```

### Before/After Model
```python
def before_model(context, agent, request):
    # Run before LLM call
    return None

def after_model(context, agent, response):
    # Run after LLM response
    return None
```

### Before/After Tool
```python
def before_tool(context, agent, tool, args):
    # Run before tool execution
    return None

def after_tool(context, agent, tool, result):
    # Run after tool execution
    return None
```

## Use Cases

- **Observability**: Log execution details
- **Security**: Validate inputs/outputs
- **State Management**: Update session state
- **Response Customization**: Modify results
- **External Integration**: Trigger notifications

## Examples

```
/google-adk:dev-callback add logging callback
/google-adk:dev-callback add input validation callback
/google-adk:dev-callback add rate limiting callback
```
