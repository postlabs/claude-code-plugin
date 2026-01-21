---
description: Create tools for agents (function, hosted, MCP)
argument-hint: [request]
allowed-tools: Read, Write, Edit, Grep, Glob
---

Create tools for OpenAI Agent SDK: $ARGUMENTS

## Tool Types

### 1. Function Tools (Most Common)

```python
from agents import function_tool, RunContextWrapper

@function_tool
def tool_name(param1: str, param2: int = 10) -> str:
    """Short description for LLM.

    More detailed explanation of when to use this tool.

    Args:
        param1: Description of param1
        param2: Description with default behavior

    Returns:
        What the tool returns
    """
    return f"Result: {param1}, {param2}"
```

### 2. Context-Aware Tools

```python
@function_tool
async def get_user_data(ctx: RunContextWrapper[MyContext]) -> str:
    """Fetch current user's data."""
    user_id = ctx.context.user_id
    return await fetch_user(user_id)
```

### 3. Hosted Tools (OpenAI Server)

```python
from agents.tools import WebSearchTool, FileSearchTool, CodeInterpreterTool

agent = Agent(
    tools=[
        WebSearchTool(),
        FileSearchTool(vector_store_ids=["vs_123"]),
        CodeInterpreterTool(),
    ],
)
```

### 4. MCP Tools

```python
from agents.mcp import MCPServerStdio

async with MCPServerStdio(
    name="Server",
    params={"command": "npx", "args": ["@mcp/server"]},
) as server:
    agent = Agent(mcp_servers=[server])
```

### 5. Agent as Tool

```python
specialist = Agent(name="Specialist", ...)

main_agent = Agent(
    tools=[
        specialist.as_tool(
            tool_name="consult_specialist",
            tool_description="Get expert analysis",
        ),
    ],
)
```

## Best Practices

1. **Clear Docstrings**: LLM uses docstring to understand tool
2. **Type Hints**: Required for schema generation
3. **Error Handling**: Return errors, don't raise exceptions
4. **Async for I/O**: Use async for network/file operations
5. **Minimal Scope**: Only request necessary capabilities

## Implementation

Create the requested tool following these patterns.
Use tool-reviewer agent to validate the implementation.
