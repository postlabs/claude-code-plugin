---
name: Google ADK - Tools
description: This skill should be used when the user asks to "create a tool", "add function tool", "use Google Search", "integrate MCP", "use OpenAPI", "create AgentTool", or needs guidance on tool types, tool parameters, or tool integration in Google ADK.
version: 1.0.0
---

# Google ADK - Tools

## Overview

Tools extend agent capabilities by allowing them to execute functions, search the web, call APIs, and delegate to other agents.

> **Latest Documentation**: Query Context7 MCP with Library ID `/google/adk-docs` for up-to-date API references.

## Tool Types

| Type | Description | Use Case |
|------|-------------|----------|
| Function Tools | Python functions | Custom logic |
| Built-in Tools | Google Search, Code Execution | Common tasks |
| AgentTool | Agent as tool | Delegation |
| MCP Tools | Model Context Protocol | External services |
| OpenAPI Tools | REST API specs | API integration |

## Function Tools

Python functions are automatically converted to tools:

```python
from google.adk import Agent

def get_weather(city: str, unit: str = "celsius") -> dict:
    """Get weather information for a city.

    Args:
        city: The city name to get weather for
        unit: Temperature unit (celsius or fahrenheit)

    Returns:
        Weather information including temperature and conditions
    """
    return {
        "status": "success",
        "city": city,
        "temperature": 22,
        "unit": unit,
        "condition": "sunny",
    }

agent = Agent(
    name="weather_bot",
    model="gemini-2.0-flash",
    tools=[get_weather],
)
```

### Return Value Best Practices

```python
def good_tool(query: str) -> dict:
    """Always include status in response."""
    try:
        result = process(query)
        return {
            "status": "success",
            "data": result,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }
```

## Built-in Tools

### Google Search

```python
from google.adk.tools import GoogleSearchTool

agent = Agent(
    name="search_agent",
    model="gemini-2.0-flash",
    tools=[GoogleSearchTool()],
)
```

### Code Execution

```python
from google.adk.tools import CodeExecutionTool

agent = Agent(
    name="code_agent",
    model="gemini-2.0-flash",
    tools=[CodeExecutionTool()],
)
```

## AgentTool

Use another agent as a tool:

```python
from google.adk import Agent, AgentTool

specialist = Agent(
    name="data_specialist",
    model="gemini-2.0-flash",
    instruction="You are a data analysis expert",
)

main_agent = Agent(
    name="coordinator",
    model="gemini-2.0-flash",
    tools=[AgentTool(agent=specialist)],
)
```

## MCP Tools

```python
from google.adk.tools import MCPTool

mcp_tool = MCPTool(
    server_url="https://mcp.example.com",
    tool_name="my_tool",
)

agent = Agent(
    name="mcp_agent",
    model="gemini-2.0-flash",
    tools=[mcp_tool],
)
```

## OpenAPI Tools

```python
from google.adk.tools import OpenAPITool

api_tool = OpenAPITool(
    spec_url="https://api.example.com/openapi.json",
)

agent = Agent(
    name="api_agent",
    model="gemini-2.0-flash",
    tools=[api_tool],
)
```

## Long-Running Tools

For async operations:

```python
from google.adk.tools import LongRunningFunctionTool

class DataProcessingTool(LongRunningFunctionTool):
    def initiate(self, data: str) -> dict:
        operation_id = start_async_processing(data)
        return {"status": "pending", "operation_id": operation_id}

    def check_status(self, operation_id: str) -> dict:
        status = get_operation_status(operation_id)
        if status.complete:
            return {"status": "success", "result": status.result}
        return {"status": "pending", "progress": status.progress}
```

## Best Practices

1. **Clear Docstrings**: LLM uses docstrings to understand tools
2. **Type Hints**: Required for schema generation
3. **Status Field**: Always include status in responses
4. **Error Handling**: Return errors, don't raise exceptions
5. **Descriptive Names**: Use action-oriented function names

## Additional Resources

For the latest API references and detailed documentation, query Context7 MCP with Library ID `/google/adk-docs`.
