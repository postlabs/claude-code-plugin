---
description: Create and run evaluations for Google ADK agents - test cases, metrics, and quality assessment.
argument-hint: "[request]"
allowed-tools: ["Read", "Write", "Edit", "Grep", "Glob", "Bash"]
---

Create and run evaluations for Google ADK agents.

## Task

Help the user create test cases and evaluate agent performance.

## Evaluation Framework

### Test Case Structure
```python
test_cases = [
    {
        "input": "What's the weather in Tokyo?",
        "expected_tool": "get_weather",
        "expected_contains": ["Tokyo"],
    },
    {
        "input": "Hello",
        "expected_intent": "greeting",
    },
    {
        "input": "Calculate 2+2",
        "expected_result": "4",
    }
]
```

### Running Evaluation
```python
from google.adk import Evaluator

evaluator = Evaluator(agent=my_agent)
results = await evaluator.run(test_cases)

print(f"Pass rate: {results.pass_rate}%")
for result in results.failures:
    print(f"Failed: {result.input} - {result.reason}")
```

## Metrics

- **Response Accuracy**: Does output match expected?
- **Tool Usage**: Correct tool selected?
- **Latency**: Response time
- **Token Usage**: Input/output tokens consumed
- **Error Rate**: Failures vs successes

## Test Case Types

### Tool Selection Tests
Verify agent selects correct tool:
```python
{"input": "Search for Python tutorials", "expected_tool": "google_search"}
```

### Content Tests
Verify response contains expected content:
```python
{"input": "What is 2+2?", "expected_contains": ["4"]}
```

### Intent Tests
Verify agent understands intent:
```python
{"input": "Thanks!", "expected_intent": "gratitude"}
```

### Edge Case Tests
Test unusual inputs:
```python
{"input": "", "expected_behavior": "handle_empty"}
{"input": "..." * 1000, "expected_behavior": "handle_long_input"}
```

## Process

1. Identify agent to evaluate
2. Create comprehensive test cases
3. Run evaluation
4. Analyze results and failures
5. Iterate on agent improvements
