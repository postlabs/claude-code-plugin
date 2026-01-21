# /openai-agent:eval

Evaluate agent performance.

## Usage

```
/openai-agent:eval [request]
```

## Evaluation Approaches

### Manual Testing
```python
test_cases = [
    {"input": "Hello", "expected": "greeting"},
    {"input": "Help with order", "expected": "order_help"},
]

for case in test_cases:
    result = Runner.run_sync(agent, case["input"])
    # Assert expectations
```

### Trace Analysis
Review traces at platform.openai.com/traces for:
- Response quality
- Tool usage patterns
- Handoff behavior

## Examples

```
/openai-agent:eval create test cases for my agent
/openai-agent:eval analyze recent traces for issues
```
