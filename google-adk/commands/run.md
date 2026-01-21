# /google-adk:run

Run agents locally.

## Usage

```
/google-adk:run [agent-file] [prompt]
```

## Examples

```
/google-adk:run agents/main_agent.py "Hello, help me"
/google-adk:run  # Interactive mode
```

## Running Agents

```python
from google.adk import Runner

# Create runner
runner = Runner(agent=my_agent)

# Run with prompt
response = await runner.run("Hello")

# Run with session
response = await runner.run("Hello", session_id="user-123")
```

## Local Development Server

```bash
adk web  # Starts local web UI for testing
```
