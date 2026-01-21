# Tool Types Reference

## Function Tools Deep Dive

### Manual Function Tool Creation

For advanced control, create tools manually:

```python
from agents import FunctionTool
import json

async def handle_invoke(ctx: ToolContext, args_json: str) -> str:
    args = json.loads(args_json)
    return f"Processed: {args}"

tool = FunctionTool(
    name="custom_tool",
    description="A custom tool with full control",
    params_json_schema={
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "Input data"},
            "options": {
                "type": "object",
                "properties": {
                    "format": {"type": "string", "enum": ["json", "text"]},
                },
            },
        },
        "required": ["input"],
    },
    on_invoke_tool=handle_invoke,
)
```

### ToolContext Access

```python
from agents import ToolContext, function_tool

@function_tool
async def context_aware_tool(ctx: ToolContext) -> str:
    print(f"Tool name: {ctx.tool_name}")
    print(f"Tool call ID: {ctx.tool_call_id}")
    print(f"Arguments: {ctx.tool_arguments}")
    return "done"
```

### Failure Handling

```python
def custom_error_handler(ctx, error):
    return f"Tool failed: {error}. Please try again with different input."

@function_tool(failure_error_function=custom_error_handler)
def risky_tool(data: str) -> str:
    if not data:
        raise ValueError("Data is required")
    return f"Processed: {data}"
```

## Hosted Tools Deep Dive

### WebSearchTool

```python
from agents.tools import WebSearchTool

tool = WebSearchTool(
    # No configuration needed - uses OpenAI's search
)

# Agent with web search
agent = Agent(
    name="Researcher",
    model="gpt-4.1",
    tools=[WebSearchTool()],
    instructions="Search the web to find current information",
)
```

### FileSearchTool

```python
from agents.tools import FileSearchTool

tool = FileSearchTool(
    vector_store_ids=["vs_abc123"],  # Pre-created vector store
    max_num_results=10,              # Max results per search
    # Vector stores created via OpenAI API:
    # client.vector_stores.create(...)
    # client.vector_stores.file_batches.create(...)
)
```

### CodeInterpreterTool

```python
from agents.tools import CodeInterpreterTool

tool = CodeInterpreterTool(
    # Executes Python in sandboxed environment
    # Can read/write files, generate charts, etc.
)

agent = Agent(
    name="DataScientist",
    model="gpt-4.1",
    tools=[CodeInterpreterTool()],
    instructions="Analyze data and create visualizations",
)
```

### ImageGenerationTool

```python
from agents.tools import ImageGenerationTool

tool = ImageGenerationTool(
    # Uses DALL-E for image generation
)

agent = Agent(
    name="Artist",
    model="gpt-4.1",
    tools=[ImageGenerationTool()],
    instructions="Create images based on descriptions",
)
```

### HostedMCPTool

```python
from agents.tools import HostedMCPTool

tool = HostedMCPTool(
    server_label="my-mcp-server",
    server_url="https://mcp.example.com",
    allowed_tools=["search", "query"],  # Restrict available tools
)
```

## Local Runtime Tools

### ComputerTool

```python
from agents.tools import ComputerTool

class MyComputer:
    async def screenshot(self) -> bytes:
        # Return screenshot as bytes
        ...

    async def click(self, x: int, y: int, button: str):
        # Perform click at coordinates
        ...

    async def scroll(self, x: int, y: int, dx: int, dy: int):
        # Scroll at position
        ...

    async def type(self, text: str):
        # Type text
        ...

    async def keypress(self, keys: list[str]):
        # Press keys
        ...

    async def drag(self, path: list[tuple[int, int]]):
        # Drag along path
        ...

computer_tool = ComputerTool(computer=MyComputer())
```

### LocalShellTool

```python
from agents.tools import LocalShellTool

shell_tool = LocalShellTool()

# WARNING: Executes shell commands locally
# Use with caution and proper sandboxing
```

### ApplyPatchTool

```python
from agents.tools import ApplyPatchTool

class MyPatchEditor:
    async def apply_patch(self, path: str, patch: str) -> str:
        # Apply patch to file
        ...

patch_tool = ApplyPatchTool(editor=MyPatchEditor())
```

## Codex Tool (Experimental)

```python
from agents.tools import codex_tool

tool = codex_tool(
    sandbox_mode="workspace-write",
    working_directory="/path/to/repo",
    default_thread_options={
        "model": "codex-1",
        "enable_web_search": True,
    },
    persist_session=True,
    skip_git_repo_check=False,
)
```

## Tool Selection Guidelines

| Use Case | Recommended Tool |
|----------|------------------|
| Custom business logic | `@function_tool` |
| Web research | `WebSearchTool` |
| Document Q&A | `FileSearchTool` |
| Data analysis | `CodeInterpreterTool` |
| Image creation | `ImageGenerationTool` |
| External APIs | MCP servers |
| Sub-agent tasks | `agent.as_tool()` |
