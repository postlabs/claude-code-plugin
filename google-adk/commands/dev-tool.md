---
name: google-adk:dev-tool
description: Create tools for Google ADK agents - function tools, built-in tools, MCP tools, OpenAPI tools, or AgentTool.
argument-hint: "[request]"
allowed-tools: ["Read", "Write", "Edit", "Grep", "Glob"]
---

Create tools for Google ADK agents.

## Task

Help the user create tools based on their requirements.

## Tool Types

### Function Tools
Python functions automatically converted to tools:
```python
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
    }

agent = Agent(tools=[get_weather])
```

### Built-in Tools
```python
from google.adk.tools import GoogleSearchTool, CodeExecutionTool

agent = Agent(tools=[GoogleSearchTool(), CodeExecutionTool()])
```

### AgentTool
Use another agent as a tool:
```python
from google.adk import AgentTool

specialist = Agent(name="specialist", ...)
main_agent = Agent(tools=[AgentTool(agent=specialist)])
```

### MCP Tools
```python
from google.adk.tools import MCPTool
mcp_tool = MCPTool(server_url="https://mcp.example.com", tool_name="my_tool")
```

### OpenAPI Tools
```python
from google.adk.tools import OpenAPITool
api_tool = OpenAPITool(spec_url="https://api.example.com/openapi.json")
```

## Requirements

- **Docstrings**: Required - LLM uses them to understand the tool
- **Type hints**: Required - Schema generation needs them
- **Return dict**: Include "status" field for success/error
- **Error handling**: Return error dict, never raise exceptions

Load the Google ADK - Tools skill for complete tool patterns.
