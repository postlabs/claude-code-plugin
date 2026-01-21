# Google ADK Plugin

Claude Code plugin for developing AI agents with [Google Agent Development Kit](https://github.com/google/adk-python).

## Commands

| Command | Description |
|---------|-------------|
| `/google-adk:init` | Initialize new agent project |
| `/google-adk:dev` | General development |
| `/google-adk:dev-agent` | Create agents (LLM, Workflow, Custom) |
| `/google-adk:dev-tool` | Create tools (Function, MCP, OpenAPI) |
| `/google-adk:dev-callback` | Configure callbacks (Before/After hooks) |
| `/google-adk:dev-multi` | Configure multi-agent systems |
| `/google-adk:run` | Run agents locally |
| `/google-adk:eval` | Evaluate with test cases |
| `/google-adk:deploy` | Deploy to Vertex AI / Cloud Run |
| `/google-adk:refactor` | Refactor agent code |
| `/google-adk:migrate` | Migrate to new SDK versions |

## Installation

```bash
/plugin install google-adk@postlabs/claude-code-plugin
```

## Requirements

- Python 3.11+ (or TypeScript/Go/Java)
- google-adk SDK

## License

MIT
