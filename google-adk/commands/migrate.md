---
name: migrate
description: Migrate Google ADK projects to new SDK versions - breaking changes, API updates, deprecations.
argument-hint: "[target-version]"
allowed-tools: ["Read", "Write", "Edit", "Grep", "Glob", "Bash"]
---

Migrate Google ADK projects to new SDK versions.

## Task

Help the user migrate their project to a new Google ADK version.

## Migration Process

### 1. Check Current Version
```bash
pip show google-adk
```

### 2. Review Release Notes
Query Context7 MCP with Library ID `/google/adk-docs` for latest migration guides and breaking changes.

### 3. Update Dependencies
```bash
pip install --upgrade google-adk
```

### 4. Identify Breaking Changes
Common migration issues:
- Import path changes
- API signature changes
- Deprecated method removal
- New required parameters

### 5. Update Code
Address each breaking change systematically.

### 6. Test Functionality
Run all tests and verify agent behavior.

## Common Migration Patterns

### Import Changes
```python
# Old
from google.adk.agents import Agent

# New
from google.adk import Agent
```

### API Changes
```python
# Old
agent = Agent(prompt="...")

# New
agent = Agent(instruction="...")
```

### Callback Signatures
```python
# Old
def callback(context, request):
    ...

# New
def callback(callback_context: CallbackContext, llm_request: LlmRequest):
    ...
```

## Process

1. Identify current SDK version
2. Check target version release notes
3. Create backup of current code
4. Update dependencies
5. Fix import statements
6. Update API calls
7. Fix callback signatures
8. Run tests
9. Verify deployment

## Rollback

If migration fails:
```bash
pip install google-adk==<previous-version>
git checkout <previous-commit>
```

Query Context7 MCP for the latest version-specific migration documentation.
