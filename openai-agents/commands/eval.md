---
name: openai-agents:eval
description: Evaluate agent performance with test cases
argument-hint: [request]
allowed-tools: Read, Write, Edit, Grep, Glob, Bash(python:*, pytest:*)
---

Evaluate agent performance: $ARGUMENTS

## Evaluation Approaches

### 1. Test Case Evaluation

```python
from agents import Agent, Runner

agent = Agent(name="Bot", instructions="...")

test_cases = [
    {
        "input": "Hello",
        "expected_behavior": "greeting",
        "criteria": ["friendly", "helpful"]
    },
    {
        "input": "Help with order #123",
        "expected_behavior": "order_lookup",
        "criteria": ["asks for details", "professional"]
    },
]

async def evaluate():
    results = []
    for case in test_cases:
        result = await Runner.run(agent, case["input"])
        score = evaluate_response(result.final_output, case)
        results.append({
            "input": case["input"],
            "output": result.final_output,
            "score": score,
        })
    return results
```

### 2. Trace Analysis

Review traces at platform.openai.com/traces:
- Response quality and coherence
- Tool usage patterns
- Handoff behavior
- Guardrail triggers
- Token usage

### 3. A/B Testing

```python
agent_a = Agent(name="AgentA", instructions="...")
agent_b = Agent(name="AgentB", instructions="...")

async def ab_test(prompt: str):
    result_a = await Runner.run(agent_a, prompt)
    result_b = await Runner.run(agent_b, prompt)

    return {
        "a": result_a.final_output,
        "b": result_b.final_output,
    }
```

### 4. Automated Evaluation

```python
evaluator = Agent(
    name="Evaluator",
    instructions="""
    Evaluate the response quality on:
    1. Accuracy (1-10)
    2. Helpfulness (1-10)
    3. Clarity (1-10)
    Provide overall score and explanation.
    """,
    output_type=EvaluationResult,
)

async def auto_evaluate(response: str, context: str):
    prompt = f"Context: {context}\nResponse: {response}"
    result = await Runner.run(evaluator, prompt)
    return result.final_output
```

## Evaluation Metrics

| Metric | Description |
|--------|-------------|
| Accuracy | Correctness of information |
| Helpfulness | How well needs are addressed |
| Clarity | Ease of understanding |
| Safety | Avoidance of harmful content |
| Latency | Response time |
| Cost | Token usage |

## Best Practices

1. **Diverse Test Cases**: Cover edge cases and common scenarios
2. **Clear Criteria**: Define what success looks like
3. **Regular Review**: Check traces periodically
4. **Compare Versions**: A/B test instruction changes
5. **Track Metrics**: Monitor over time

## Implementation

Create evaluation approach for the agent.
Run tests and report findings.
Suggest improvements based on results.
