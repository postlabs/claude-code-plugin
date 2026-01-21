---
name: openai-agents:dev
description: General development assistance for OpenAI Agent SDK projects
argument-hint: [request]
allowed-tools: Read, Write, Edit, Grep, Glob, Bash(python:*, pip:*, pytest:*)
---

Assist with OpenAI Agent SDK development: $ARGUMENTS

## Context Gathering

First, understand the current project:
1. Check for existing agents in `agents/` directory
2. Look for tools in `tools/` directory
3. Review configuration in `config/` or settings files
4. Check installed SDK version in requirements.txt or pyproject.toml

## Development Guidelines

When implementing features, follow OpenAI Agent SDK best practices:

### Agent Design
- Use clear, specific instructions
- Choose appropriate model (gpt-4.1 default, gpt-5.2 for complex reasoning)
- Apply single responsibility principle
- Include proper type hints

### Tools
- Use @function_tool decorator
- Write clear docstrings for LLM understanding
- Add type hints for schema generation
- Handle errors gracefully

### Handoffs
- Set handoff_description on target agents
- Use input_filter for sensitive data
- Avoid circular handoff patterns

### Guardrails
- Use blocking mode for critical checks
- Include informative output_info
- Handle exceptions properly

### Sessions
- Choose appropriate session type for use case
- Use unique session_id per user/conversation
- Consider encryption for sensitive data

## Implementation

Address the user's request following the guidelines above.
Use the openai-agents-sdk skills for reference as needed.
