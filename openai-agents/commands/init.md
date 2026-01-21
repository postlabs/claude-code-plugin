---
description: Initialize a new OpenAI Agent SDK project with best practices
argument-hint: [project-name]
allowed-tools: Read, Write, Bash(mkdir:*, python:*, pip:*, uv:*)
---

Initialize a new OpenAI Agent SDK project named "$ARGUMENTS" (or in current directory if no name provided).

## Project Structure to Create

```
$ARGUMENTS/
├── agents/
│   └── main_agent.py      # Entry point agent
├── tools/
│   └── __init__.py        # Custom tools
├── config/
│   └── settings.py        # Configuration
├── tests/
│   └── test_agent.py      # Agent tests
├── pyproject.toml         # Project metadata
├── requirements.txt       # Dependencies
├── .env.example           # Environment template
└── README.md              # Project documentation
```

## Implementation Steps

1. Create directory structure
2. Set up virtual environment using `uv` or `python -m venv`
3. Install dependencies: `pip install openai-agents`
4. Create main_agent.py with basic agent template:

```python
from agents import Agent, Runner

agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant.",
    model="gpt-4.1",
)

if __name__ == "__main__":
    result = Runner.run_sync(agent, "Hello!")
    print(result.final_output)
```

5. Create .env.example with OPENAI_API_KEY placeholder
6. Create README with usage instructions

## Best Practices to Apply

- Use environment variables for API keys
- Include type hints in all code
- Set up proper project structure for scalability
- Include basic test setup
