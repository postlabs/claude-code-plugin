---
name: run
description: Run Google ADK agents locally - execute agents, start dev UI, or run API server.
argument-hint: "[agent-file] [prompt]"
allowed-tools: ["Read", "Bash", "Glob"]
---

Run Google ADK agents locally.

## Task

Help the user run their agents for testing and development.

## Running Methods

### CLI Execution
```bash
adk run agents/main_agent.py "Hello, help me"
```

### Dev UI (Browser)
```bash
adk web
```
Starts a local web interface for interactive testing.

### API Server
```bash
adk api_server --port 8080
```
Starts an HTTP API server for integration testing.

### Programmatic Execution
```python
from google.adk import Runner

runner = Runner(agent=my_agent)

# Synchronous
response = runner.run_sync(user_input="Hello")

# Asynchronous
response = await runner.run(user_input="Hello")

# With session
response = await runner.run(
    user_input="Hello",
    session_id="user-123"
)

# Streaming
async for chunk in runner.run_stream(user_input="Hello"):
    print(chunk.content, end="")
```

## Environment Setup

Ensure environment variables are set:
```bash
export GOOGLE_API_KEY=your_api_key
# Or for Vertex AI:
export GOOGLE_GENAI_USE_VERTEXAI=TRUE
export GOOGLE_CLOUD_PROJECT=your_project
```

## Process

1. Identify the agent file to run
2. Check environment variables are configured
3. Execute using appropriate method (CLI, API, or programmatic)
4. Monitor output for errors or unexpected behavior
