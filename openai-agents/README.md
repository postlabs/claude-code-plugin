# OpenAI Agent SDK Plugin

Claude Code plugin for developing AI agents with [OpenAI Agent SDK](https://github.com/openai/openai-agents-python).

## Commands

| Command | Description |
|---------|-------------|
| `/openai-agent:init` | Initialize new agent project |
| `/openai-agent:dev` | General development |
| `/openai-agent:dev-agent` | Create/modify agents |
| `/openai-agent:dev-tool` | Create tools (function, hosted, MCP) |
| `/openai-agent:dev-handoff` | Configure handoffs between agents |
| `/openai-agent:dev-guardrail` | Add input/output guardrails |
| `/openai-agent:dev-session` | Configure sessions and memory |
| `/openai-agent:run` | Run and test agents |
| `/openai-agent:trace` | Configure and view traces |
| `/openai-agent:eval` | Evaluate agent performance |
| `/openai-agent:refactor` | Refactor agent code |
| `/openai-agent:migrate` | Migrate to new SDK versions |

## Installation

```bash
/plugin install openai-agents@postlabs/claude-code-plugin
```

## Requirements

- Python 3.11+
- openai-agents SDK

## License

MIT
