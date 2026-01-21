# Agent Patterns and Architectures

## Router Pattern

Central agent that routes requests to specialized agents:

```python
from agents import Agent

support_agent = Agent(
    name="Support",
    instructions="Handle customer support inquiries",
    handoff_description="Transfer for support issues",
)

billing_agent = Agent(
    name="Billing",
    instructions="Handle billing questions",
    handoff_description="Transfer for billing issues",
)

router = Agent(
    name="Router",
    instructions="Route users to the appropriate department based on their needs",
    handoffs=[support_agent, billing_agent],
)
```

## Pipeline Pattern

Sequential processing through multiple agents:

```python
from agents import Agent, Runner

analyzer = Agent(
    name="Analyzer",
    instructions="Analyze the input and extract key information",
    output_type=AnalysisResult,
)

processor = Agent(
    name="Processor",
    instructions="Process the analysis and generate recommendations",
)

# Pipeline execution
analysis = await Runner.run(analyzer, user_input)
result = await Runner.run(processor, str(analysis.final_output))
```

## Specialist Team Pattern

Main agent with specialized sub-agents as tools:

```python
from agents import Agent

researcher = Agent(
    name="Researcher",
    instructions="Research topics and gather information",
)

writer = Agent(
    name="Writer",
    instructions="Write clear, engaging content",
)

editor = Agent(
    name="Editor",
    instructions="Edit and improve written content",
)

manager = Agent(
    name="ContentManager",
    tools=[
        researcher.as_tool(
            tool_name="research",
            tool_description="Research a topic",
        ),
        writer.as_tool(
            tool_name="write",
            tool_description="Write content",
        ),
        editor.as_tool(
            tool_name="edit",
            tool_description="Edit content",
        ),
    ],
)
```

## Hierarchical Pattern

Multi-level agent structure:

```python
# Level 1: Entry point
greeter = Agent(
    name="Greeter",
    instructions="Welcome users and understand their needs",
    handoffs=[sales_router, support_router],
)

# Level 2: Department routers
sales_router = Agent(
    name="SalesRouter",
    handoffs=[new_customer_agent, existing_customer_agent],
)

support_router = Agent(
    name="SupportRouter",
    handoffs=[technical_agent, billing_agent],
)

# Level 3: Specialists
new_customer_agent = Agent(name="NewCustomer", ...)
existing_customer_agent = Agent(name="ExistingCustomer", ...)
```

## Validation Pattern

Agent with guardrails for safe operation:

```python
from agents import Agent, input_guardrail, output_guardrail

@input_guardrail
async def check_harmful_content(ctx, agent, input_text):
    # Validate input safety
    ...

@output_guardrail
async def check_pii(ctx, agent, output_text):
    # Check for personal information
    ...

safe_agent = Agent(
    name="SafeAgent",
    instructions="Provide helpful information safely",
    input_guardrails=[check_harmful_content],
    output_guardrails=[check_pii],
)
```

## Context-Aware Pattern

Agent with rich context access:

```python
from dataclasses import dataclass
from agents import Agent, RunContextWrapper

@dataclass
class AppContext:
    user_id: str
    user_tier: str
    db_connection: Any
    feature_flags: dict

def personalized_instructions(ctx: RunContextWrapper[AppContext], agent):
    tier = ctx.context.user_tier
    if tier == "premium":
        return "Provide premium support with priority handling"
    return "Provide standard support"

agent = Agent(
    name="ContextAware",
    instructions=personalized_instructions,
)
```
