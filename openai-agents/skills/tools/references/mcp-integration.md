# MCP Integration Reference

## MCP Server Types

### MCPServerStdio

Local process-based MCP server. Best for:
- Local file system access
- Development and testing
- Bundled tools with the application

```python
from agents.mcp import MCPServerStdio

# Filesystem server
async with MCPServerStdio(
    name="Filesystem",
    params={
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"],
    },
) as fs_server:
    agent = Agent(mcp_servers=[fs_server])

# Custom Python server
async with MCPServerStdio(
    name="CustomServer",
    params={
        "command": "python",
        "args": ["-m", "my_mcp_server"],
        "env": {"API_KEY": os.environ["API_KEY"]},
    },
) as custom_server:
    agent = Agent(mcp_servers=[custom_server])
```

### MCPServerStreamableHttp

Remote HTTP-based MCP server. Best for:
- Shared team servers
- Cloud-hosted services
- Production deployments

```python
from agents.mcp import MCPServerStreamableHttp

async with MCPServerStreamableHttp(
    name="RemoteServer",
    params={
        "url": "https://mcp.example.com/mcp",
        "headers": {
            "Authorization": f"Bearer {token}",
            "X-Custom-Header": "value",
        },
        "timeout": 30,
    },
    cache_tools_list=True,       # Cache tool definitions
    max_retry_attempts=3,         # Retry on failure
    retry_backoff_seconds_base=2, # Exponential backoff
) as server:
    agent = Agent(mcp_servers=[server])

    # Invalidate cache when needed
    await server.invalidate_tools_cache()
```

## Common MCP Servers

### Filesystem Server

```python
# Read/write files in a directory
MCPServerStdio(
    name="Files",
    params={
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"],
    },
)
```

### PostgreSQL Server

```python
MCPServerStdio(
    name="Database",
    params={
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres"],
        "env": {
            "POSTGRES_URL": "postgresql://user:pass@localhost/db",
        },
    },
)
```

### GitHub Server

```python
MCPServerStdio(
    name="GitHub",
    params={
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {
            "GITHUB_TOKEN": os.environ["GITHUB_TOKEN"],
        },
    },
)
```

### Brave Search Server

```python
MCPServerStdio(
    name="BraveSearch",
    params={
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env": {
            "BRAVE_API_KEY": os.environ["BRAVE_API_KEY"],
        },
    },
)
```

## Multiple MCP Servers

```python
async with (
    MCPServerStdio(name="Files", params={...}) as files,
    MCPServerStdio(name="Database", params={...}) as db,
    MCPServerStreamableHttp(name="API", params={...}) as api,
):
    agent = Agent(
        name="MultiToolAgent",
        mcp_servers=[files, db, api],
        instructions="Use files, database, and API as needed",
    )
```

## Error Handling

```python
from agents.mcp import MCPConnectionError, MCPToolError

try:
    async with MCPServerStdio(name="Server", params={...}) as server:
        agent = Agent(mcp_servers=[server])
        result = await Runner.run(agent, "Use MCP tool")
except MCPConnectionError as e:
    print(f"Failed to connect to MCP server: {e}")
except MCPToolError as e:
    print(f"MCP tool execution failed: {e}")
```

## Best Practices

1. **Use Context Managers**: Always use `async with` for proper cleanup
2. **Environment Variables**: Never hardcode credentials in code
3. **Caching**: Enable `cache_tools_list=True` for frequently used servers
4. **Timeouts**: Set appropriate timeouts for network operations
5. **Retry Logic**: Configure retries for unreliable connections
6. **Minimal Permissions**: Only grant necessary file/API access
