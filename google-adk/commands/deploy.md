# /google-adk:deploy

Deploy agents to production.

## Usage

```
/google-adk:deploy [target]
```

## Deployment Targets

### Vertex AI Agent Engine
```bash
adk deploy vertex-ai \
  --project=my-project \
  --region=us-central1 \
  --agent=agents/main_agent.py
```

### Cloud Run
```bash
adk deploy cloud-run \
  --project=my-project \
  --region=us-central1
```

### Docker
```bash
adk build docker
docker run -p 8080:8080 my-agent
```

## Configuration

### Dockerfile
```dockerfile
FROM google/adk-runtime:latest
COPY . /app
CMD ["adk", "serve"]
```

### Environment Variables
```
GOOGLE_CLOUD_PROJECT=my-project
GEMINI_API_KEY=...
```

## Examples

```
/google-adk:deploy to Vertex AI
/google-adk:deploy create Dockerfile
/google-adk:deploy configure Cloud Run
```
