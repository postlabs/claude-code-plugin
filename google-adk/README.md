# Google ADK Plugin

Claude Code plugin for developing AI agents with [Google Agent Development Kit](https://github.com/google/adk-python).

## Features

- **6 Specialized Skills** for progressive learning and context-efficient guidance
- **3 Autonomous Agents** for validation, review, and architecture design
- **11 Commands** for project lifecycle management

## Skills

| Skill | Trigger Phrases |
|-------|-----------------|
| **agents** | "create agent", "configure agent", "agent instruction" |
| **tools** | "create tool", "function tool", "MCP integration" |
| **workflows** | "SequentialAgent", "ParallelAgent", "LoopAgent" |
| **callbacks** | "add callback", "guardrails", "before_model_callback" |
| **multi-agent** | "multi-agent system", "agent routing", "sub_agents" |
| **deployment** | "deploy agent", "Vertex AI", "Cloud Run" |

## Agents

| Agent | Purpose |
|-------|---------|
| **agent-validator** | Validates agent configurations and identifies issues |
| **tool-reviewer** | Reviews tool definitions for best practices |
| **architecture-advisor** | Designs multi-agent architectures and patterns |

## Commands

| Command | Description |
|---------|-------------|
| `/google-adk:init` | Initialize new agent project |
| `/google-adk:dev` | General development assistance |
| `/google-adk:dev-agent` | Create agents (LLM, Workflow, Custom) |
| `/google-adk:dev-tool` | Create tools (Function, MCP, OpenAPI) |
| `/google-adk:dev-callback` | Configure callbacks (guardrails, logging) |
| `/google-adk:dev-multi` | Design multi-agent systems |
| `/google-adk:run` | Run agents locally |
| `/google-adk:eval` | Evaluate with test cases |
| `/google-adk:deploy` | Deploy to Vertex AI / Cloud Run / Docker |
| `/google-adk:refactor` | Refactor agent code |
| `/google-adk:migrate` | Migrate to new SDK versions |

## Quick Start

```bash
# Initialize a new project
/google-adk:init my-agent

# Create an agent
/google-adk:dev-agent create a customer support agent

# Add tools
/google-adk:dev-tool add Google Search capability

# Run locally
/google-adk:run
```

## Installation

```bash
/plugin install google-adk@postlabs/claude-code-plugin
```

## Requirements

- Python 3.11+
- google-adk SDK
- Google API Key or Vertex AI credentials

## Environment Variables

```bash
# Google AI Studio
export GOOGLE_API_KEY=your_api_key

# Or Vertex AI
export GOOGLE_GENAI_USE_VERTEXAI=TRUE
export GOOGLE_CLOUD_PROJECT=your_project
export GOOGLE_CLOUD_REGION=us-central1
```

## License

MIT
