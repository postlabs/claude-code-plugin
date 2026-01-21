---
description: General development assistance for Google ADK projects - modifying agents, improving code, adding features.
argument-hint: "[request]"
allowed-tools: ["Read", "Write", "Edit", "Grep", "Glob", "Bash"]
---

Provide general development assistance for Google ADK projects.

## Task

Help the user with their development request using Google ADK best practices.

## Process

1. Understand the user's request
2. Explore the codebase to understand current structure
3. Identify which skills are relevant:
   - Agent creation/modification → Google ADK - Agent Creation skill
   - Tool development → Google ADK - Tools skill
   - Workflow patterns → Google ADK - Workflow Agents skill
   - Callbacks/hooks → Google ADK - Callbacks skill
   - Multi-agent systems → Google ADK - Multi-Agent Systems skill
   - Deployment → Google ADK - Deployment skill
4. Load relevant skill(s) for detailed guidance
5. Implement the requested changes

## Common Requests

- "Add error handling" → Implement try/except, return error dicts from tools
- "Add logging" → Add callback for observability
- "Improve instructions" → Enhance agent instruction clarity
- "Add a new capability" → Create tool or sub-agent
- "Make it faster" → Consider parallel agents, optimize tools

## Best Practices

- Always include type hints on tool functions
- Always include docstrings on tools (LLM needs them)
- Return dicts with status field from tools
- Use output_key for state communication between agents
- Keep agent instructions clear and focused

Query Context7 MCP with Library ID `/google/adk-docs` for latest API references if needed.
