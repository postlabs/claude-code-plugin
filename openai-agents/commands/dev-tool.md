# /openai-agent:dev-tool

Create tools for agents.

## Usage

```
/openai-agent:dev-tool [request]
```

## Tool Types

### Function Tools
```python
@function_tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {city}: Sunny"
```

### Hosted Tools
- WebSearchTool
- FileSearchTool
- CodeInterpreterTool
- ImageGenerationTool

### Agents as Tools
```python
agent.as_tool(tool_name="helper", tool_description="...")
```

## Examples

```
/openai-agent:dev-tool create a function tool to fetch user data
/openai-agent:dev-tool add web search capability
/openai-agent:dev-tool convert my helper agent to a tool
```
