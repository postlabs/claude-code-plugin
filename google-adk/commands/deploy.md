---
description: Deploy Google ADK agents to production - Vertex AI, Cloud Run, Docker, or GKE.
argument-hint: "[target]"
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob"]
---

Deploy Google ADK agents to production.

## Task

Help the user deploy their agents to the target platform.

## Deployment Targets

| Target | Use Case | Scaling |
|--------|----------|---------|
| Vertex AI | Production | Managed |
| Cloud Run | Serverless | Auto-scaling |
| Docker/GKE | Custom | Manual/Auto |

## Vertex AI Agent Engine

Managed deployment with automatic scaling:
```bash
adk deploy vertex-ai \
    --project=my-project \
    --region=us-central1 \
    --agent=agents/main_agent.py
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

### Dockerfile
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

## GKE Deployment

```yaml
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

## Best Practices

1. Never hardcode API keys - use environment variables or secrets
2. Add health check endpoints
3. Enable structured logging
4. Use Cloud Secret Manager for sensitive data
5. Configure appropriate resource limits

Load the Google ADK - Deployment skill for complete deployment guidance.
