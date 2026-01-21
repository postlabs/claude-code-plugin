# OpenAI Agent SDK Plugin

Claude Code plugin for developing AI agents with [OpenAI Agent SDK](https://github.com/openai/openai-agents-python).

## Features

### Skills (6)

Specialized knowledge for different SDK aspects:

| Skill | Triggers On |
|-------|-------------|
| **agents** | "create an agent", "configure agent", "dynamic instructions" |
| **tools** | "create a tool", "function tool", "MCP integration" |
| **handoffs** | "configure handoffs", "agent routing", "multi-agent" |
| **guardrails** | "add guardrails", "validate input", "detect PII" |
| **sessions** | "add session", "persist conversation", "encrypted session" |
| **tracing** | "configure tracing", "debug agent", "custom span" |

### Agents (3)

Autonomous agents for development assistance:

| Agent | Purpose |
|-------|---------|
| **agent-validator** | Validates agent code for best practices |
| **tool-reviewer** | Reviews tool definitions for correctness |
| **architecture-advisor** | Designs multi-agent architectures |

### Commands (12)

| Command | Description |
|---------|-------------|
| `/openai-agents:init` | Initialize new agent project |
| `/openai-agents:dev` | General development assistance |
| `/openai-agents:dev-agent` | Create/modify agents |
| `/openai-agents:dev-tool` | Create tools (function, hosted, MCP) |
| `/openai-agents:dev-handoff` | Configure handoffs |
| `/openai-agents:dev-guardrail` | Add guardrails |
| `/openai-agents:dev-session` | Configure sessions |
| `/openai-agents:run` | Run and test agents |
| `/openai-agents:trace` | Configure tracing |
| `/openai-agents:eval` | Evaluate performance |
| `/openai-agents:refactor` | Refactor agent code |
| `/openai-agents:migrate` | Migrate SDK versions |

## Installation

```bash
# Install plugin (when published)
/plugin install openai-agents

# Or use locally
cc --plugin-dir /path/to/openai-agents
```

## Requirements

- Python 3.11+
- openai-agents SDK (`pip install openai-agents`)
- OPENAI_API_KEY environment variable

## Quick Start

```bash
# Initialize a new project
/openai-agents:init my-project

# Create an agent
/openai-agents:dev-agent create a customer support agent

# Add tools
/openai-agents:dev-tool add a function to fetch user data

# Run the agent
/openai-agents:run
```

## SDK Reference

For the latest SDK documentation, skills will use Context7 MCP with Library ID `/openai/openai-agents-python`.

## License

MIT
