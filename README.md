# Postlabs Claude Code Plugins

A curated collection of Claude Code plugins for AI agent development. Build production-ready AI agents with OpenAI Agents SDK and Google ADK.

## Available Plugins

| Plugin | Description | Version |
|--------|-------------|---------|
| [openai-agents](./openai-agents) | Build AI agents with OpenAI Agents SDK | 0.2.1 |
| [google-adk](./google-adk) | Build AI agents with Google ADK | 0.2.1 |

## Installation

### Method 1: Add Marketplace (Recommended)

```bash
# Add this marketplace
/plugin marketplace add postlabs/claude-code-plugin

# Browse available plugins
/plugin menu

# Install individual plugins
/plugin install openai-agents@postlabs-plugins
/plugin install google-adk@postlabs-plugins
```

### Method 2: Direct Installation

```bash
/plugin install openai-agents@postlabs/claude-code-plugin
/plugin install google-adk@postlabs/claude-code-plugin
```

### Method 3: Local Development

```bash
git clone https://github.com/postlabs/claude-code-plugin.git
cc --plugin-dir ./claude-code-plugin/openai-agents
```

## Plugins

### openai-agents

Claude Code plugin for developing AI agents with [OpenAI Agents SDK](https://github.com/openai/openai-agents-python).

**Features:**
- 6 Skills: agents, tools, handoffs, guardrails, sessions, tracing
- 3 Agents: agent-validator, tool-reviewer, architecture-advisor
- 12 Commands: init, dev, dev-agent, dev-tool, dev-handoff, dev-guardrail, dev-session, run, trace, eval, refactor, migrate

**Requirements:**
- Python 3.9+
- `pip install openai-agents`
- `OPENAI_API_KEY` environment variable

**Quick Start:**
```bash
/openai-agents:init my-project
/openai-agents:dev-agent create a customer support agent
/openai-agents:run
```

[View full documentation](./openai-agents/README.md)

---

### google-adk

Claude Code plugin for developing AI agents with [Google Agent Development Kit](https://github.com/google/adk-python).

**Features:**
- 6 Skills: agents, tools, workflows, callbacks, multi-agent, deployment
- 3 Agents: agent-validator, tool-reviewer, architecture-advisor
- 11 Commands: init, dev, dev-agent, dev-tool, dev-callback, dev-multi, run, eval, deploy, refactor, migrate

**Requirements:**
- Python 3.11+
- `pip install google-adk`
- `GOOGLE_API_KEY` or Vertex AI credentials

**Quick Start:**
```bash
/google-adk:init my-project
/google-adk:dev-agent create a customer support agent
/google-adk:run
```

[View full documentation](./google-adk/README.md)

## Repository Structure

```
claude-code-plugin/
├── .claude-plugin/
│   └── marketplace.json     # Marketplace manifest
├── openai-agents/           # OpenAI Agents SDK plugin
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── skills/              # 6 specialized skills
│   ├── agents/              # 3 autonomous agents
│   └── commands/            # 12 slash commands
├── google-adk/              # Google ADK plugin
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── skills/              # 6 specialized skills
│   ├── agents/              # 3 autonomous agents
│   └── commands/            # 11 slash commands
└── README.md
```

## Plugin Development

Each plugin follows the Claude Code plugin structure:

```
plugin-name/
├── .claude-plugin/
│   └── plugin.json          # Plugin metadata (required)
├── skills/                  # Specialized knowledge (optional)
│   └── skill-name/
│       └── SKILL.md
├── agents/                  # Autonomous agents (optional)
│   └── agent-name.md
├── commands/                # Slash commands (optional)
│   └── command-name.md
└── README.md
```

## Contributing

Contributions are welcome! Please ensure your changes:

1. Follow the existing plugin structure
2. Include proper documentation
3. Pass validation: `/plugin validate .`

## Security Notice

Make sure you trust a plugin before installing. Review the source code and understand what the plugin does before use.

## Resources

- [Claude Code Plugin Documentation](https://docs.anthropic.com/en/docs/claude-code/plugins)
- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python)
- [Google ADK](https://github.com/google/adk-python)
- [Official Claude Plugins](https://github.com/anthropics/claude-plugins-official)

## License

MIT

## Author

[Postlabs](https://github.com/postlabs)
