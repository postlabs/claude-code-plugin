---
name: google-adk:init
description: Initialize a new Google ADK project with standard structure, dependencies, and a basic agent template.
argument-hint: "[project-name]"
allowed-tools: ["Read", "Write", "Bash", "Glob"]
---

Initialize a new Google ADK project.

## Task

Create a complete Google ADK project with the following structure:

```
{project-name}/
├── agents/
│   └── main_agent.py      # Entry point agent
├── tools/                  # Custom tools
├── tests/                  # Test files
├── pyproject.toml         # Project configuration
├── requirements.txt       # Dependencies
├── .env.example           # Environment template
└── README.md              # Documentation
```

## Implementation Steps

1. Create the directory structure
2. Create `pyproject.toml` with google-adk dependency
3. Create `requirements.txt` with google-adk
4. Create `.env.example` with required environment variables
5. Create a basic agent in `agents/main_agent.py`:

```python
from google.adk import Agent

agent = Agent(
    name="assistant",
    model="gemini-2.0-flash",
    instruction="You are a helpful assistant.",
    tools=[],
)
```

6. Create README with setup instructions
7. Suggest running: `pip install -r requirements.txt`

## Environment Variables

Include in `.env.example`:
```
GOOGLE_API_KEY=your_api_key_here
# Or for Vertex AI:
# GOOGLE_GENAI_USE_VERTEXAI=TRUE
# GOOGLE_CLOUD_PROJECT=your_project
# GOOGLE_CLOUD_REGION=us-central1
```

Use the Google ADK - Agent Creation skill for Agent configuration details.
