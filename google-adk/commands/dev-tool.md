# /google-adk:dev-tool

Create tools for agents.

## Usage

```
/google-adk:dev-tool [request]
```

## Tool Types

### Function Tools
```python
from google.adk import FunctionTool

def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {city}: Sunny"

tool = FunctionTool(func=get_weather)
```

### Pre-built Tools

#### Gemini Tools
- Google Search
- Code Execution
- Computer Use

#### Google Cloud Tools
- BigQuery
- Spanner
- Vertex AI Search
- RAG Engine

#### Third-party Tools
- GitHub, Asana, Notion, Linear
- Stripe, PayPal
- And more...

### MCP Tools
```python
from google.adk import MCPTool
tool = MCPTool(server_url="...")
```

### OpenAPI Tools
```python
from google.adk import OpenAPITool
tool = OpenAPITool(spec_url="https://api.example.com/openapi.json")
```

## Examples

```
/google-adk:dev-tool create a function tool for database queries
/google-adk:dev-tool add Google Search capability
/google-adk:dev-tool integrate with GitHub API
```
