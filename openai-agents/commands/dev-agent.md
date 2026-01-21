# /openai-agent:dev-agent

Create or modify agents.

## Usage

```
/openai-agent:dev-agent [request]
```

## Examples

```
/openai-agent:dev-agent create a customer support agent
/openai-agent:dev-agent add instructions to handle refunds
/openai-agent:dev-agent make the agent more concise
```

## Agent Configuration

- name: Agent identifier
- instructions: System prompt
- model: LLM model to use
- tools: Available tools
- handoffs: Other agents to delegate to
- guardrails: Input/output validation
