---
name: openai-agents:migrate
description: Migrate to new OpenAI Agent SDK versions
argument-hint: [target-version]
allowed-tools: Read, Write, Edit, Grep, Glob, Bash(pip:*, python:*)
---

Migrate OpenAI Agent SDK to version: $ARGUMENTS

## Migration Process

### 1. Check Current Version

```bash
pip show openai-agents
```

### 2. Review Release Notes

Check GitHub releases and changelog for breaking changes:
- https://github.com/openai/openai-agents-python/releases

### 3. Update Dependency

```bash
pip install openai-agents==$ARGUMENTS
# or
pip install openai-agents --upgrade
```

### 4. Common Migration Patterns

#### Import Changes
```python
# Check for renamed imports
from agents import Agent, Runner  # Current
# May change in future versions
```

#### API Changes
```python
# Parameter renames
Agent(instructions="...")  # Check parameter names

# Method changes
Runner.run_sync(...)  # Check method signatures
```

#### Deprecated Features
```python
# Check for deprecation warnings
import warnings
warnings.filterwarnings("error", category=DeprecationWarning)
```

### 5. Test After Migration

```python
# Run test suite
pytest tests/

# Manual verification
from agents import Agent, Runner
agent = Agent(name="Test", instructions="Hello")
result = Runner.run_sync(agent, "Hi")
print(result.final_output)
```

## Migration Checklist

- [ ] Check current version
- [ ] Review release notes for breaking changes
- [ ] Update requirements.txt/pyproject.toml
- [ ] Install new version
- [ ] Fix import changes
- [ ] Update deprecated API calls
- [ ] Run tests
- [ ] Verify in development
- [ ] Deploy to staging
- [ ] Monitor for issues

## Rollback Plan

If issues occur:

```bash
# Revert to previous version
pip install openai-agents==<previous-version>
```

Keep `requirements.txt` in version control for easy rollback.

## Best Practices

1. **Test First**: Always test in development
2. **Incremental Updates**: Update one version at a time
3. **Read Changelogs**: Check for breaking changes
4. **Pin Versions**: Use exact versions in production
5. **Monitor**: Watch for issues after deployment

## Implementation

Check current SDK version.
Identify breaking changes for target version.
Apply necessary code updates.
Test functionality after migration.
