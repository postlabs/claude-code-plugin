---
name: OpenAI Agents SDK - Tools
description: This skill should be used when the user asks to "create a tool", "add function tool", "use hosted tools", "integrate MCP server", "configure web search", "add file search", "use code interpreter", "make agent as tool", or needs guidance on @function_tool decorator, tool types, tool parameters, or tool return types in OpenAI Agents SDK.
version: 1.0.0
---

# OpenAI Agents SDK - Tools

## Overview

Tools extend agent capabilities by allowing them to execute code, search the web, process files, and integrate with external services. OpenAI Agents SDK supports multiple tool types for different use cases.

> **Latest Documentation**: Query Context7 MCP with Library ID `/openai/openai-agents-python` for up-to-date API references.

## Tool Types

| Type | Description | Execution |
|------|-------------|-----------|
| Function Tools | Custom Python functions | Local |
| Hosted Tools | OpenAI-managed tools | Server-side |
| MCP Tools | Model Context Protocol servers | Local/Remote |
| Agents as Tools | Other agents as callable tools | Nested execution |

## Function Tools

### Basic Function Tool

```python
from agents import Agent, function_tool

@function_tool
def get_weather(city: str, unit: str = "celsius") -> str:
    """Get current weather for a city.

    Args:
        city: The city name to get weather for
        unit: Temperature unit (celsius or fahrenheit)

    Returns:
        Weather information string
    """
    return f"Weather in {city}: 22°{unit[0].upper()}, Sunny"

agent = Agent(
    name="WeatherBot",
    tools=[get_weather],
)
```

### Function Tool with Context

```python
from agents import function_tool, RunContextWrapper

@function_tool
async def get_user_data(ctx: RunContextWrapper[MyContext]) -> str:
    """Fetch data for current user."""
    user_id = ctx.context.user_id
    db = ctx.context.db_connection
    return await db.fetch_user(user_id)
```

### Function Tool Options

```python
@function_tool(
    name_override="fetch_weather",      # Custom tool name
    use_docstring_info=True,            # Extract description from docstring
    failure_error_function=custom_err,  # Custom error handler
)
async def get_weather(city: str) -> str:
    """Get weather information."""
    ...
```

### Return Types

```python
from agents import function_tool, ToolOutputText, ToolOutputImage, ToolOutputFileContent

@function_tool
def text_result() -> str:
    return "Simple text"

@function_tool
def image_result() -> ToolOutputImage:
    return ToolOutputImage(
        image_data=base64_data,
        media_type="image/png",
    )

@function_tool
def file_result() -> ToolOutputFileContent:
    return ToolOutputFileContent(
        file_content=bytes_data,
        media_type="application/pdf",
    )

# Multiple outputs
@function_tool
def multi_result() -> list:
    return [
        ToolOutputText(text="Here's the image:"),
        ToolOutputImage(image_data=data, media_type="image/png"),
    ]
```

## Hosted Tools

OpenAI-managed tools that run on OpenAI servers:

```python
from agents import Agent
from agents.tools import (
    WebSearchTool,
    FileSearchTool,
    CodeInterpreterTool,
    ImageGenerationTool,
    HostedMCPTool,
)

agent = Agent(
    name="ResearchBot",
    model="gpt-4.1",  # Requires OpenAI model
    tools=[
        WebSearchTool(),
        FileSearchTool(
            vector_store_ids=["vs_123"],
            max_num_results=10,
        ),
        CodeInterpreterTool(),
        ImageGenerationTool(),
        HostedMCPTool(
            server_label="my-server",
            server_url="https://mcp.example.com",
            allowed_tools=["tool1", "tool2"],
        ),
    ],
)
```

## MCP Tools

### Stdio MCP Server (Local)

```python
from agents import Agent
from agents.mcp import MCPServerStdio

async with MCPServerStdio(
    name="Filesystem",
    params={
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"],
    },
) as server:
    agent = Agent(name="FileBot", mcp_servers=[server])
    result = await Runner.run(agent, "List files")
```

### HTTP MCP Server (Remote)

```python
from agents.mcp import MCPServerStreamableHttp

async with MCPServerStreamableHttp(
    name="RemoteServer",
    params={
        "url": "https://mcp.example.com/mcp",
        "headers": {"Authorization": "Bearer token"},
        "timeout": 30,
    },
    cache_tools_list=True,
    max_retry_attempts=3,
) as server:
    agent = Agent(name="RemoteBot", mcp_servers=[server])
```

## Agents as Tools

Convert an agent into a tool for another agent:

```python
from agents import Agent

specialist = Agent(
    name="DataAnalyst",
    instructions="Analyze data and provide insights",
)

def extract_summary(result) -> str:
    return result.final_output[:200]

main_agent = Agent(
    name="Manager",
    tools=[
        specialist.as_tool(
            tool_name="analyze_data",
            tool_description="Analyze data and get insights",
            custom_output_extractor=extract_summary,
            is_enabled=True,  # or callable: (ctx, agent) -> bool
        ),
    ],
)
```

## Best Practices

1. **Clear Docstrings**: Tool descriptions come from docstrings - be specific
2. **Type Hints**: Always use type hints for automatic schema generation
3. **Error Handling**: Return meaningful error messages, don't raise exceptions
4. **Async When Needed**: Use async for I/O operations
5. **Minimal Permissions**: Only request necessary capabilities

## Additional Resources

### Reference Files

- **`references/tool-types.md`** - Detailed guide for each tool type
- **`references/mcp-integration.md`** - MCP server configuration patterns

### Example Files

- **`examples/function-tools.py`** - Various function tool patterns
- **`examples/hosted-tools.py`** - Using OpenAI hosted tools
- **`examples/mcp-tools.py`** - MCP server integration
