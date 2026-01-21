# /google-adk:eval

Evaluate agent performance with test cases.

## Usage

```
/google-adk:eval [request]
```

## Evaluation Framework

### Test Cases
```python
test_cases = [
    {
        "input": "What's the weather in Tokyo?",
        "expected_tool": "get_weather",
        "expected_contains": ["Tokyo"]
    },
    {
        "input": "Hello",
        "expected_intent": "greeting"
    }
]
```

### Running Evaluation
```python
from google.adk import Evaluator

evaluator = Evaluator(agent=my_agent)
results = await evaluator.run(test_cases)

print(f"Pass rate: {results.pass_rate}%")
```

### Metrics
- Response accuracy
- Tool usage correctness
- Latency
- Token usage

## Examples

```
/google-adk:eval create test cases for my agent
/google-adk:eval run evaluation and show results
/google-adk:eval add edge case tests
```
