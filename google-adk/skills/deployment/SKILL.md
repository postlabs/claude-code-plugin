---
name: Google ADK - Deployment
description: This skill should be used when the user asks to "deploy agent", "use Vertex AI", "deploy to Cloud Run", "create Docker container", "configure API server", "set up production", or needs guidance on deployment targets, environment configuration, or production setup in Google ADK.
version: 1.0.0
---

# Google ADK - Deployment

## Overview

Google ADK supports multiple deployment targets: local development, Vertex AI Agent Engine, Cloud Run, and Docker containers.

> **Latest Documentation**: Query Context7 MCP with Library ID `/google/adk-docs` for up-to-date API references.

## Deployment Targets

| Target | Use Case | Scaling |
|--------|----------|---------|
| Local | Development | Single instance |
| Vertex AI | Production | Managed |
| Cloud Run | Serverless | Auto-scaling |
| Docker/GKE | Custom | Manual/Auto |

## Local Development

### Dev UI (Browser)

```bash
adk web
```

### Terminal Execution

```bash
adk run agent.py
```

### API Server

```bash
adk api_server --port 8080
```

## Vertex AI Agent Engine

Managed deployment with automatic scaling:

```bash
adk deploy vertex-ai \
    --project=my-project \
    --region=us-central1 \
    --agent=agent.py
```

### Prerequisites
- Google Cloud project with billing
- Vertex AI API enabled
- Application Default Credentials

```bash
gcloud auth application-default login
gcloud config set project my-project
```

## Cloud Run

Serverless deployment:

```bash
adk deploy cloud-run \
    --project=my-project \
    --region=us-central1
```

## Docker Deployment

### Basic Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["adk", "api_server", "--host", "0.0.0.0", "--port", "8080"]
```

### Build and Run

```bash
docker build -t my-agent .
docker run -p 8080:8080 -e GOOGLE_API_KEY=$GOOGLE_API_KEY my-agent
```

### GKE Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-deployment
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: agent
        image: gcr.io/my-project/my-agent
        ports:
        - containerPort: 8080
        env:
        - name: GOOGLE_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-secrets
              key: google-api-key
```

## Environment Variables

### Google AI Studio

```bash
export GOOGLE_API_KEY=your_api_key
```

### Vertex AI

```bash
export GOOGLE_GENAI_USE_VERTEXAI=TRUE
export GOOGLE_CLOUD_PROJECT=your_project
export GOOGLE_CLOUD_REGION=us-central1
```

### .env File

```bash
# .env
GOOGLE_API_KEY=your_api_key
# Or for Vertex AI:
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=your_project
GOOGLE_CLOUD_REGION=us-central1
```

## Authentication

### Development (Local)

```bash
gcloud auth application-default login
```

### Production (Service Account)

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

### In Docker

```dockerfile
COPY service-account.json /app/
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/service-account.json
```

## Programmatic Execution

```python
from google.adk import Agent, Runner

agent = Agent(
    name="assistant",
    model="gemini-2.0-flash",
    instruction="You are helpful",
)

runner = Runner(agent=agent)

# Sync
response = runner.run_sync(user_input="Hello")

# Async
response = await runner.run(user_input="Hello")

# Streaming
async for chunk in runner.run_stream(user_input="Hello"):
    print(chunk.content, end="")
```

## Best Practices

1. **Environment Variables**: Never hardcode API keys
2. **Service Accounts**: Use for production
3. **Health Checks**: Add /health endpoint
4. **Logging**: Enable structured logging
5. **Secrets Management**: Use Cloud Secret Manager

## Additional Resources

For the latest API references and detailed documentation, query Context7 MCP with Library ID `/google/adk-docs`.
